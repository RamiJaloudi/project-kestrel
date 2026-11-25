"""Real LangGraph, offline providers and isolated checkpointers; no matter DB."""
import json
import threading
import time
from collections import Counter
from contextlib import contextmanager

import pytest
pytest.importorskip('langgraph', reason='Install the pinned optional DDR dependencies to run the graph integration tests')
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from kestrel.ddr.evidence import validate_bundle, validate_draft
from kestrel.ddr.graph import DdrEngine, GraphFault
from kestrel.ddr.providers import ChatOpenAIProvider, FakeProvider
from kestrel.ddr.schemas import (ApprovalReceipt, ArtifactRef, Citation, Claim, DraftReport, EvidenceBundle,
    EvidenceItem, Limits, RunSpec, Usage, canonical, digest)


def fixture_data():
    text = '😀 First original sentence. SECRET_SOURCE_703 is a synthetic evidence token.'
    start = text.index('SECRET_SOURCE_703')
    citation = Citation(evidence_id='evidence-1', finding_ref='reviewed-finding-1', source_version_id='source-v1',
        source_bytes_hash=digest('original-bytes'), source_text_hash=digest(text), unit=1,
        start=start, end=start + len('SECRET_SOURCE_703'), quote='SECRET_SOURCE_703')
    item = EvidenceItem(id='evidence-1', finding_ref='reviewed-finding-1', severity='high',
        summary='SECRET_REVIEWED_SUMMARY_819', citation=citation, unit_text=text,
        unit_text_hash=digest(text), quote_hash=digest(citation.quote))
    spec = RunSpec(run_id='run-1', requester_id='requester', matter_id='matter-1', snapshot_hash=digest('snapshot'),
        config_hash=digest('approved-config'), finding_refs=('reviewed-finding-1',), deadline_epoch=100000 + 604800)
    return spec, EvidenceBundle(snapshot_hash=spec.snapshot_hash, config_hash=spec.config_hash, items=(item,))


class MemoryPorts:
    """Test double for the required external durable attempt/artifact/approval DB."""
    def __init__(self, spec, evidence):
        self.evidence_value = evidence
        self.spec = spec
        self.revoked = False
        self.reviewer_cleared = True
        self.artifacts = {}
        self.attempts = {}
        self.uncertain = set()
        self.step_locks = {}
        self.lock = threading.RLock()
        self.reservations = {}
        self.calls = 0
        self.tokens = 0
        self.cost = 0
        self.receipt = None
        self.tasks = {}
        self.completed = Counter()
        self.crash_after = None
        self.parallel_barrier = None
        self.active = 0
        self.max_active = 0
        self.external_actor = False
    def authorize(self, spec, stage):
        if self.revoked or self.external_actor:
            raise PermissionError('Current authority denied')
        if spec.snapshot_hash != self.spec.snapshot_hash or spec.config_hash != self.spec.config_hash:
            raise GraphFault('STALE_SCOPE')
    def evidence(self, spec):
        return self.evidence_value
    def execute_once(self, spec, step, input_hash, producer):
        key = (spec.run_id, step)
        with self.lock:
            step_lock = self.step_locks.setdefault(key, threading.Lock())
        with step_lock:
            if key in self.uncertain:
                raise GraphFault('ATTEMPT_UNCERTAIN')
            if key in self.attempts:
                prior_hash, reference = self.attempts[key]
                if input_hash != prior_hash:
                    raise GraphFault('ATTEMPT_INPUT_CHANGED')
                return reference
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            try:
                if self.parallel_barrier and step in {'quality', 'citations'}:
                    self.parallel_barrier.wait(timeout=3)
                artifact = producer()
                reference = ArtifactRef(id='artifact-' + step, kind=artifact.kind,
                    content_hash=digest(canonical(artifact)), creator_id='draft-creator')
                self.artifacts[reference.id] = artifact
                self.attempts[key] = (input_hash, reference)
                self.completed[step] += 1
            except Exception:
                self.uncertain.add(key)
                raise
            finally:
                with self.lock:
                    self.active -= 1
            if self.crash_after == step:
                self.crash_after = None
                raise RuntimeError('Synthetic crash after durable artifact commit')
            return reference
    def artifact(self, spec, reference):
        return self.artifacts[reference.id]
    def reserve(self, spec, step, estimated_input_tokens, max_output_tokens, live):
        with self.lock:
            if live:
                raise PermissionError('Paid providers disabled in isolated tests')
            if self.calls >= spec.limits.max_model_calls or self.tokens + estimated_input_tokens + max_output_tokens > spec.limits.total_tokens:
                raise GraphFault('AGGREGATE_BUDGET')
            self.calls += 1
            key = 'reservation-' + str(self.calls)
            self.reservations[key] = (estimated_input_tokens + max_output_tokens, None)
            return key
    def settle(self, spec, reservation, usage, uncertain):
        with self.lock:
            estimate, _ = self.reservations[reservation]
            self.reservations[reservation] = (estimate, usage)
            self.tokens += estimate if uncertain else usage.input_tokens + usage.output_tokens
            self.cost += 0 if uncertain else usage.cost_cents
            if self.tokens > spec.limits.total_tokens or self.cost > spec.limits.max_cost_cents:
                raise GraphFault('AGGREGATE_BUDGET')
    def review_task(self, spec, draft, validation, key):
        self.tasks.setdefault(key, 'review-task-1')
        return self.tasks[key]
    def approval(self, spec, draft, validation):
        if self.receipt and not self.reviewer_cleared:
            raise PermissionError('Independent reviewer source clearance denied')
        return self.receipt
    def approve(self, **changes):
        draft = self.attempts[(self.spec.run_id, 'draft')][1]
        self.receipt = ApprovalReceipt(id='human-decision-1', decision='approve', reviewer_id='independent-attorney',
            draft_hash=draft.content_hash, snapshot_hash=self.spec.snapshot_hash, config_hash=self.spec.config_hash,
        ).model_copy(update=changes)


def setup_engine(provider=None, checkpointer=None):
    spec, evidence = fixture_data()
    ports = MemoryPorts(spec, evidence)
    provider = provider or FakeProvider()
    engine = DdrEngine(ports, provider, checkpointer or InMemorySaver(), clock=lambda: 100000)
    return spec, ports, provider, engine


def test_real_graph_interrupt_ack_is_not_approval_and_replay_is_idempotent():
    spec, ports, provider, engine = setup_engine()
    initial = engine.start(spec)
    assert initial['phase'] == 'awaiting_attorney' and initial['__interrupt__']
    assert provider.calls == ['contracts', 'draft', 'quality'] and len(ports.tasks) == 1
    assert engine.start(spec)['phase'] == 'awaiting_attorney'
    still_pending = engine.resume(spec)
    assert still_pending['phase'] == 'awaiting_attorney' and still_pending['__interrupt__']
    assert provider.calls == ['contracts', 'draft', 'quality'] and len(ports.tasks) == 1
    ports.approve()
    approved = engine.resume(spec)
    assert approved['phase'] == 'internally_approved'
    assert engine.resume(spec)['approval_ref'] == 'human-decision-1'
    assert ports.completed == Counter({'contracts': 1, 'draft': 1, 'quality': 1, 'citations': 1})


def test_sqlite_checkpoints_resume_in_reconstructed_engine_and_contain_no_passages(tmp_path):
    spec, evidence = fixture_data()
    ports, provider = MemoryPorts(spec, evidence), FakeProvider()
    path = tmp_path / 'isolated-checkpoints.db'
    with SqliteSaver.from_conn_string(str(path)) as saver:
        engine = DdrEngine(ports, provider, saver, clock=lambda: 100000)
        assert engine.start(spec)['phase'] == 'awaiting_attorney'
    assert b'SECRET_SOURCE_703' not in path.read_bytes()
    assert b'SECRET_REVIEWED_SUMMARY_819' not in path.read_bytes()
    fresh_provider = FakeProvider()
    with SqliteSaver.from_conn_string(str(path)) as saver:
        resumed = DdrEngine(ports, fresh_provider, saver, clock=lambda: 100600)
        assert resumed.start(spec)['phase'] == 'awaiting_attorney'
        ports.approve()
        assert resumed.resume(spec)['phase'] == 'internally_approved'
        checkpoint = json.dumps(resumed.status(spec))
        assert 'SECRET_SOURCE_703' not in checkpoint and 'SECRET_REVIEWED_SUMMARY_819' not in checkpoint
    assert fresh_provider.calls == [] and len(provider.calls) == 3


def test_committed_step_crash_continues_pending_nodes_without_duplicate_provider_call():
    spec, ports, provider, engine = setup_engine()
    ports.crash_after = 'contracts'
    with pytest.raises(RuntimeError, match='Synthetic crash'):
        engine.start(spec)
    assert provider.calls == ['contracts']
    rebuilt = DdrEngine(ports, provider, engine._graph.checkpointer, clock=lambda: 100001)
    recovered = rebuilt.continue_run(spec)
    assert recovered['phase'] == 'awaiting_attorney'
    assert provider.calls == ['contracts', 'draft', 'quality']
    assert ports.completed['contracts'] == 1


@pytest.mark.parametrize('change', ['revoked', 'snapshot', 'config', 'reviewer'])
def test_resume_rechecks_current_requester_snapshot_config_and_approver_clearance(change):
    spec, ports, provider, engine = setup_engine()
    engine.start(spec)
    ports.approve()
    if change == 'revoked':
        ports.revoked = True
    elif change in {'snapshot', 'config'}:
        ports.spec = spec.model_copy(update={change + '_hash': digest('changed')})
    else:
        ports.reviewer_cleared = False
    with pytest.raises((PermissionError, GraphFault)):
        engine.resume(spec)
    assert len(provider.calls) == 3


@pytest.mark.parametrize('changes', [
    {'reviewer_id': 'requester'}, {'reviewer_id': 'draft-creator'},
    {'draft_hash': digest('different')}, {'snapshot_hash': digest('different')}, {'config_hash': digest('different')},
])
def test_graph_cannot_accept_self_approval_or_a_receipt_for_other_exact_content(changes):
    spec, ports, _, engine = setup_engine()
    engine.start(spec)
    ports.approve(**changes)
    with pytest.raises(GraphFault, match='APPROVAL_INVALID'):
        engine.resume(spec)


def test_rejection_is_final_and_does_not_publish_or_start_another_model_attempt():
    spec, ports, provider, engine = setup_engine()
    engine.start(spec)
    ports.approve(decision='reject')
    assert engine.resume(spec)['phase'] == 'rejected'
    assert provider.calls == ['contracts', 'draft', 'quality']
    assert not hasattr(ports, 'release') and not hasattr(ports, 'approve_report')


def test_quality_failure_blocks_before_review_and_parallelism_is_bounded():
    spec, ports, _, engine = setup_engine(FakeProvider(quality_passed=False))
    ports.parallel_barrier = threading.Barrier(2)
    result = engine.start(spec)
    assert result['phase'] == 'blocked_validation' and not ports.tasks
    assert ports.max_active == 2


def test_citation_unicode_exactness_hashes_and_approved_severity_are_required():
    spec, evidence = fixture_data()
    item = evidence.items[0]
    draft = DraftReport(title='Draft', claims=(Claim(finding_ref=item.finding_ref, text=item.summary,
        severity=item.severity, citations=(item.citation,)),))
    assert validate_draft(spec, evidence, draft).passed
    changed = item.citation.model_copy(update={'start': item.citation.start + 1})
    malformed = evidence.model_copy(update={'items': (item.model_copy(update={'citation': changed}),)})
    assert not validate_bundle(spec, malformed).passed
    modified = draft.model_copy(update={'claims': (draft.claims[0].model_copy(update={'severity': 'low'}),)})
    assert any(i.code == 'severity_changed' for i in validate_draft(spec, evidence, modified).issues)
    tampered = evidence.model_copy(update={'items': (item.model_copy(update={'unit_text': item.unit_text + 'tamper'}),)})
    assert any(i.code == 'unit_hash' for i in validate_bundle(spec, tampered).issues)
    missing = spec.model_copy(update={'finding_refs': (*spec.finding_refs, 'missing-reviewed-finding')})
    assert any(i.reference == 'missing-reviewed-finding' for i in validate_bundle(missing, evidence).issues)


def test_revocation_during_provider_completion_withholds_artifact_and_raw_checkpoint():
    spec, ports, _, engine = setup_engine()
    class RevokingProvider(FakeProvider):
        def invoke(self, *args):
            value = super().invoke(*args)
            ports.revoked = True
            return value
    engine.provider = RevokingProvider()
    with pytest.raises(PermissionError):
        engine.start(spec)
    assert not ports.artifacts
    ports.revoked = False
    assert 'SECRET_SOURCE_703' not in json.dumps(engine.status(spec))


def test_ambiguous_provider_failure_retains_reservation_and_is_never_auto_retried():
    class FailingProvider(FakeProvider):
        def invoke(self, *args):
            self.calls.append('contracts')
            raise RuntimeError('SECRET_PROVIDER_EXCEPTION')
    spec, ports, provider, engine = setup_engine(FailingProvider())
    with pytest.raises(GraphFault, match='PROVIDER_UNCERTAIN') as failure:
        engine.start(spec)
    assert 'SECRET_PROVIDER_EXCEPTION' not in str(failure.value)
    with pytest.raises(GraphFault, match='ATTEMPT_UNCERTAIN'):
        engine.continue_run(spec)
    assert provider.calls == ['contracts'] and ports.tokens > 0


def test_execution_deadline_and_aggregate_budget_refuse_work_without_paid_calls():
    spec, ports, provider, engine = setup_engine()
    with pytest.raises(GraphFault, match='DEADLINE_EXCEEDED'):
        engine.start(spec, active_deadline_epoch=99999)
    ports.external_actor = True
    with pytest.raises(PermissionError):
        engine.start(spec)
    ports.external_actor = False
    too_small = spec.model_copy(update={'limits': Limits(total_tokens=1)})
    with pytest.raises(GraphFault, match='AGGREGATE_BUDGET'):
        engine.start(too_small)
    assert provider.calls == []


def test_live_langchain_adapter_is_explicitly_disabled_and_does_not_construct_client(monkeypatch):
    from decimal import Decimal
    import langchain_openai
    calls = []
    monkeypatch.setattr(langchain_openai, 'ChatOpenAI', lambda **kwargs: calls.append(kwargs))
    spec, _ = fixture_data()
    provider = ChatOpenAIProvider(model='unapproved-model', api_key='synthetic-unused-key', profile_hash=spec.config_hash,
        input_usd_per_million=Decimal('1'), output_usd_per_million=Decimal('1'))
    with pytest.raises(PermissionError):
        provider.invoke(spec, 'contracts', {}, 10)
    assert calls == []


def test_resume_rejects_external_draft_tampering_before_using_approval_receipt():
    spec, ports, _, engine = setup_engine()
    engine.start(spec)
    ports.approve()
    reference = ports.attempts[(spec.run_id, 'draft')][1]
    draft = ports.artifacts[reference.id]
    ports.artifacts[reference.id] = draft.model_copy(update={'title': 'Changed after review'})
    with pytest.raises(GraphFault, match='ARTIFACT_INTEGRITY'):
        engine.resume(spec)


def test_active_deadline_is_fresh_after_a_long_human_pause_but_bounds_execution():
    now = [100000]
    spec, ports, provider, engine = setup_engine()
    engine.clock = lambda: now[0]
    assert engine.start(spec, active_deadline_epoch=now[0] + 5)['phase'] == 'awaiting_attorney'
    now[0] += 3600
    ports.approve()
    assert engine.resume(spec, active_deadline_epoch=now[0] + 5)['phase'] == 'internally_approved'
    assert len(provider.calls) == 3


def test_provider_completion_after_active_deadline_does_not_persist_an_artifact():
    now = [100000]
    spec, ports, _, engine = setup_engine()
    engine.clock = lambda: now[0]
    class SlowProvider(FakeProvider):
        def invoke(self, *args):
            value = super().invoke(*args)
            now[0] += 6
            return value
    engine.provider = SlowProvider()
    with pytest.raises(GraphFault, match='DEADLINE_EXCEEDED'):
        engine.start(spec, active_deadline_epoch=now[0] + 5)
    assert not ports.artifacts
