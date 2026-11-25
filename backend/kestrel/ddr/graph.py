"""Actual LangGraph with opaque checkpoints and external human authority.

The caller must supply a private checkpointer and durable GraphPorts. Knowing a
thread ID is never access authority. This foundation is not an application job
queue, a legal approval service, or a production persistence implementation.
"""
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypedDict
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from langsmith import tracing_context
from .evidence import validate_bundle, validate_draft
from .ports import GraphPorts
from .providers import Provider
from .schemas import (ArtifactRef, CitationValidation, DraftReport, QualityReview,
                      RunSpec, SpecialistResult, canonical, digest)


class GraphFault(RuntimeError):
    """Safe fixed error code; never include evidence/provider exception contents."""


class State(TypedDict, total=False):
    spec: dict
    phase: str
    specialist_ref: dict
    draft_ref: dict
    quality_ref: dict
    validation_ref: dict
    task_ref: str
    approval_ref: str


class DdrEngine:
    def __init__(self, ports: GraphPorts, provider: Provider, checkpointer, *, clock=time.time):
        if checkpointer is None:
            raise ValueError('An explicit private checkpointer is required')
        self.ports, self.provider, self.clock = ports, provider, clock
        self._active_deadline = ContextVar('ddr_active_deadline', default=None)
        builder = StateGraph(State)
        for name, node in [('coordinator', self._coordinator), ('contracts', self._contracts),
                           ('draft', self._draft), ('quality', self._quality), ('citations', self._citations),
                           ('join', self._join), ('review_task', self._review_task), ('human_gate', self._human_gate)]:
            builder.add_node(name, node)
        builder.add_edge(START, 'coordinator')
        builder.add_edge('coordinator', 'contracts')
        builder.add_edge('contracts', 'draft')
        builder.add_edge('draft', 'quality')
        builder.add_edge('draft', 'citations')
        builder.add_edge(['quality', 'citations'], 'join')
        builder.add_conditional_edges('join', lambda state: 'review_task' if state['phase'] == 'ready_for_review' else END)
        builder.add_edge('review_task', 'human_gate')
        builder.add_edge('human_gate', END)
        self._graph = builder.compile(checkpointer=checkpointer)

    def _authorize(self, spec, stage):
        deadline = self._active_deadline.get()
        if self.clock() >= spec.deadline_epoch or deadline is not None and self.clock() >= deadline:
            raise GraphFault('DEADLINE_EXCEEDED')
        self.ports.authorize(spec, stage)

    @contextmanager
    def _execution(self, active_deadline_epoch):
        now = self.clock()
        deadline = min(active_deadline_epoch if active_deadline_epoch is not None else now + 120, now + 120)
        if deadline <= now:
            raise GraphFault('DEADLINE_EXCEEDED')
        token = self._active_deadline.set(deadline)
        try:
            with tracing_context(enabled=False):
                yield
        finally:
            self._active_deadline.reset(token)

    def _spec(self, state):
        return RunSpec.model_validate(state['spec'])

    def _bundle(self, spec):
        self._authorize(spec, 'evidence.before')
        bundle = self.ports.evidence(spec)
        self._authorize(spec, 'evidence.after')
        if not validate_bundle(spec, bundle).passed:
            raise GraphFault('EVIDENCE_INVALID')
        return bundle

    def _read(self, spec, raw, expected):
        reference = ArtifactRef.model_validate(raw)
        self._authorize(spec, 'artifact.before')
        artifact = self.ports.artifact(spec, reference)
        self._authorize(spec, 'artifact.after')
        if not isinstance(artifact, expected) or artifact.kind != reference.kind or digest(canonical(artifact)) != reference.content_hash:
            raise GraphFault('ARTIFACT_INTEGRITY')
        return artifact

    def _once(self, spec, stage, inputs, producer):
        self._authorize(spec, stage + '.before')
        input_hash = digest(canonical({'snapshot': spec.snapshot_hash, 'config': spec.config_hash, 'inputs': inputs}))
        reference = self.ports.execute_once(spec, stage, input_hash, producer)
        self._authorize(spec, stage + '.after')
        return reference.model_dump(mode='json')

    def _model(self, spec, stage, payload):
        self._authorize(spec, 'provider.' + stage + '.before')
        estimated = max(1, (len(canonical(payload)) + 2) // 3)
        if hasattr(self.provider, 'estimate_input_tokens'):
            estimated = self.provider.estimate_input_tokens(stage, payload)
        reservation = self.ports.reserve(spec, stage, estimated, spec.limits.max_output_tokens, self.provider.live)
        try:
            result = self.provider.invoke(spec, stage, payload, spec.limits.max_output_tokens)
        except Exception:
            self.ports.settle(spec, reservation, None, True)
            raise GraphFault('PROVIDER_UNCERTAIN') from None
        self.ports.settle(spec, reservation, result.usage, False)
        self._authorize(spec, 'provider.' + stage + '.after')
        if result.usage.output_tokens > spec.limits.max_output_tokens or result.usage.input_tokens + result.usage.output_tokens > spec.limits.total_tokens:
            raise GraphFault('PROVIDER_BUDGET_EXCEEDED')
        expected = {'contracts': SpecialistResult, 'draft': DraftReport, 'quality': QualityReview}[stage]
        if not isinstance(result.artifact, expected):
            raise GraphFault('PROVIDER_SCHEMA')
        return result.artifact

    def _coordinator(self, state):
        spec = self._spec(state)
        self._authorize(spec, 'coordinator')
        if spec.limits.max_model_calls < 3:
            raise GraphFault('MODEL_CALL_BUDGET')
        self._bundle(spec)
        return {'phase': 'running'}

    def _contracts(self, state):
        spec = self._spec(state)
        bundle = self._bundle(spec)
        ref = self._once(spec, 'contracts', {'snapshot': spec.snapshot_hash},
                         lambda: self._model(spec, 'contracts', {'evidence': bundle.model_dump(mode='json')}))
        return {'specialist_ref': ref}

    def _draft(self, state):
        spec = self._spec(state)
        specialist = self._read(spec, state['specialist_ref'], SpecialistResult)
        ref = self._once(spec, 'draft', state['specialist_ref'],
                         lambda: self._model(spec, 'draft', {'specialist': specialist.model_dump(mode='json')}))
        return {'draft_ref': ref}

    def _quality(self, state):
        spec = self._spec(state)
        draft = self._read(spec, state['draft_ref'], DraftReport)
        bundle = self._bundle(spec)
        ref = self._once(spec, 'quality', state['draft_ref'], lambda: self._model(spec, 'quality', {
            'draft': draft.model_dump(mode='json'), 'evidence': bundle.model_dump(mode='json')}))
        return {'quality_ref': ref}

    def _citations(self, state):
        spec = self._spec(state)
        draft = self._read(spec, state['draft_ref'], DraftReport)
        bundle = self._bundle(spec)
        ref = self._once(spec, 'citations', state['draft_ref'], lambda: validate_draft(spec, bundle, draft))
        return {'validation_ref': ref}

    def _join(self, state):
        spec = self._spec(state)
        self._authorize(spec, 'join')
        quality = self._read(spec, state['quality_ref'], QualityReview)
        validation = self._read(spec, state['validation_ref'], CitationValidation)
        return {'phase': 'ready_for_review' if quality.passed and validation.passed else 'blocked_validation'}

    def _review_task(self, state):
        spec = self._spec(state)
        self._authorize(spec, 'review_task.before')
        task = self.ports.review_task(spec, ArtifactRef.model_validate(state['draft_ref']),
            ArtifactRef.model_validate(state['validation_ref']), digest(spec.run_id + ':attorney-review:' + state['draft_ref']['content_hash']))
        self._authorize(spec, 'review_task.after')
        if not isinstance(task, str) or re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', task) is None:
            raise GraphFault('REVIEW_TASK_INVALID')
        return {'task_ref': task, 'phase': 'awaiting_attorney'}

    def _human_gate(self, state):
        spec = self._spec(state)
        self._authorize(spec, 'human_gate.before')
        draft, validation = ArtifactRef.model_validate(state['draft_ref']), ArtifactRef.model_validate(state['validation_ref'])
        draft_value = self._read(spec, state['draft_ref'], DraftReport)
        quality_value = self._read(spec, state['quality_ref'], QualityReview)
        validation_value = self._read(spec, state['validation_ref'], CitationValidation)
        if not quality_value.passed or not validation_value.passed or not validate_draft(spec, self._bundle(spec), draft_value).passed:
            raise GraphFault('REVIEW_EVIDENCE_INVALID')
        # The acknowledgement is ignored. Only the authenticated external record
        # can supply a decision; repeated pending resumes interrupt again.
        while True:
            receipt = self.ports.approval(spec, draft, validation)
            self._authorize(spec, 'human_gate.current')
            if receipt is not None:
                break
            interrupt({'run_id': spec.run_id, 'task_ref': state['task_ref'], 'draft_ref': draft.id})
            self._authorize(spec, 'human_gate.resumed')
            self._bundle(spec)
        if (receipt.reviewer_id in {spec.requester_id, draft.creator_id}
            or receipt.draft_hash != draft.content_hash or receipt.snapshot_hash != spec.snapshot_hash
            or receipt.config_hash != spec.config_hash):
            raise GraphFault('APPROVAL_INVALID')
        self._authorize(spec, 'human_gate.after')
        return {'approval_ref': receipt.id, 'phase': 'internally_approved' if receipt.decision == 'approve' else 'rejected'}

    def _config(self, spec):
        return {'configurable': {'thread_id': digest(canonical(spec))},
                'max_concurrency': spec.limits.max_concurrency, 'recursion_limit': spec.limits.recursion_limit,
                'callbacks': []}

    def start(self, spec: RunSpec, *, active_deadline_epoch=None):
        with self._execution(active_deadline_epoch):
            self._authorize(spec, 'start')
            current = self._graph.get_state(self._config(spec))
            if current.values:
                if current.values.get('spec') != spec.model_dump(mode='json'):
                    raise GraphFault('CHECKPOINT_SCOPE')
                interrupts = tuple(i for task in current.tasks for i in task.interrupts)
                if current.next and not interrupts:
                    # Complete durable producers are deduplicated by execute_once.
                    # An ambiguous paid attempt must be refused by that ledger.
                    return self._graph.invoke(None, self._config(spec))
                return dict(current.values, **({'__interrupt__': interrupts} if interrupts else {}))
            return self._graph.invoke({'spec': spec.model_dump(mode='json')}, self._config(spec))

    def resume(self, spec: RunSpec, *, active_deadline_epoch=None):
        with self._execution(active_deadline_epoch):
            self._authorize(spec, 'resume')
            self._bundle(spec)
            current = self._graph.get_state(self._config(spec))
            if not current.values or current.values.get('spec') != spec.model_dump(mode='json'):
                raise GraphFault('CHECKPOINT_SCOPE')
            if not current.next:
                return dict(current.values)
            if not any(task.interrupts for task in current.tasks):
                raise GraphFault('NO_PENDING_REVIEW')
            return self._graph.invoke(Command(resume={'acknowledged': True}), self._config(spec))

    def continue_run(self, spec: RunSpec, *, active_deadline_epoch=None):
        return self.start(spec, active_deadline_epoch=active_deadline_epoch)

    def status(self, spec: RunSpec):
        self._authorize(spec, 'status')
        with tracing_context(enabled=False):
            value = self._graph.get_state(self._config(spec))
            return dict(value.values)
