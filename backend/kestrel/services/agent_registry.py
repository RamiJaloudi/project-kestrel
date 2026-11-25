"""Technical drafts, independent legal publication, and explicit rerun authority.

Publication records impacts/tasks only. It never creates an analysis/DDR job,
changes an approved finding, approves a report, or releases material externally.
"""
import json
from fastapi import HTTPException
from sqlalchemy import select
from kestrel import models as m
from kestrel.domain import Organization as O, Role as R, member_and_not_walled
from kestrel.repositories.identity import principal
from kestrel.schemas.agent_registry import Definition, AGENTS, TOOLS, MODELS
from kestrel.services import workflow as w, review_work as rw, lifecycle
from kestrel.services.auth import clock, audit
from kestrel.adapters.extraction import canonical, digest
from kestrel.services.action_center import diff


def access(actor, matter, roles=None):
    if actor.org != O.FIRM or not member_and_not_walled(actor, matter):
        raise HTTPException(403, 'Agent registry scope denied')
    if roles is not None and not actor.roles.intersection(roles):
        raise HTTPException(403, 'Scoped agent governance role required')


def actor_for(db, account_id):
    account = db.get(m.Account, account_id)
    if not account or not account.active:
        raise HTTPException(403, 'Current independent authority required')
    return principal(db, account, clock())


def catalog():
    return {'agents': AGENTS, 'tools': TOOLS, 'models': MODELS,
        'notice': 'Registry definitions do not implement every specialist. Only server tools execute; no access, legal approval or release tool is available.'}


def events(db, version):
    return list(db.scalars(select(m.AgentProfileEvent).where(m.AgentProfileEvent.version_id == version.id).order_by(m.AgentProfileEvent.created_at, m.AgentProfileEvent.id)))


def event_map(db, version):
    values = events(db, version)
    if any(item.content_hash != version.content_hash for item in values):
        raise HTTPException(409, 'Agent version event integrity denied')
    return {item.operation: item for item in values}


def checked(db, version):
    if version is None:
        raise HTTPException(404, 'Agent version unavailable')
    definition = Definition.model_validate_json(version.definition_json)
    material = {'profile_id': version.profile_id, 'matter_id': version.matter_id, 'revision': version.revision,
        'previous_id': version.previous_id, 'base_published_id': version.base_published_id,
        'definition': definition.model_dump(mode='json'), 'rationale': version.rationale, 'created_by': version.created_by}
    if digest(canonical(material).encode()) != version.content_hash:
        raise HTTPException(409, 'Agent version integrity denied')
    return definition


def state(db, version):
    operations = event_map(db, version)
    if 'archive' in operations: return 'archived'
    if 'publish' in operations: return 'replaced' if db.scalar(select(m.AgentProfileReplacement.id).where(m.AgentProfileReplacement.old_version_id == version.id)) else 'published'
    if 'reject' in operations: return 'rejected'
    if 'approve' in operations: return 'approved'
    if 'submit' in operations: return 'submitted'
    return 'tested' if 'test' in operations else 'draft'


def eligible_version(db, version, *, for_new_run=True):
    definition = checked(db, version)
    operations = event_map(db, version)
    if not {'test', 'submit', 'approve', 'publish'} <= operations.keys() or 'archive' in operations or 'reject' in operations:
        raise HTTPException(409, 'Current tested independently published agent version required')
    approval = operations['approve']
    approver = actor_for(db, approval.actor_id)
    access(approver, version.matter_id, {R.SME})
    if approver.id == version.created_by:
        raise HTTPException(403, 'Independent legal agent approver required')
    if for_new_run and db.scalar(select(m.AgentProfileReplacement.id).where(m.AgentProfileReplacement.old_version_id == version.id)):
        raise HTTPException(409, 'Agent version replaced; select its current successor')
    return definition


def resolve_versions(db, actor, version_ids, *, for_new_run=True):
    if not version_ids or len(version_ids) > 14 or len(set(version_ids)) != len(version_ids):
        raise HTTPException(422, 'One to fourteen distinct published agent version IDs required')
    values = []
    kinds = set()
    matter = None
    for version_id in sorted(version_ids):
        version = db.get(m.AgentProfileVersion, version_id)
        if version is None: raise HTTPException(404, 'Agent version unavailable')
        w.legal(actor, version.matter_id)
        if matter is not None and version.matter_id != matter: raise HTTPException(403, 'Agent profiles must share the requested matter')
        matter = version.matter_id
        definition = eligible_version(db, version, for_new_run=for_new_run)
        if definition.agent_kind in kinds: raise HTTPException(422, 'One profile per specialist role required')
        kinds.add(definition.agent_kind)
        values.append({'id': version.id, 'profile_id': version.profile_id, 'matter_id': version.matter_id,
            'content_hash': version.content_hash, 'definition': definition.model_dump(mode='json')})
    return {'agent_profile_ids': [value['id'] for value in values], 'profiles': values,
        'hash': digest(canonical(values).encode())}


def output(db, actor, version):
    access(actor, version.matter_id, {R.ROOT_ADMIN, R.SME})
    definition = checked(db, version)
    profile = db.get(m.AgentProfile, version.profile_id)
    return {'id': version.id, 'profile_id': profile.id, 'matter_id': version.matter_id, 'name': profile.name,
        'revision': version.revision, 'previous_id': version.previous_id, 'base_published_id': version.base_published_id,
        'definition': definition.model_dump(mode='json'), 'content_hash': version.content_hash, 'state': state(db, version),
        'created_by': version.created_by, 'rationale': version.rationale,
        'is_author': actor.id == version.created_by, 'can_manage': R.ROOT_ADMIN in actor.roles,
        'can_approve': R.SME in actor.roles and actor.id != version.created_by,
        'events': [{'operation': item.operation, 'actor_id': item.actor_id, 'rationale': item.rationale,
                    'report': json.loads(item.report_json), 'created_at': item.created_at} for item in events(db, version)]}


def listing(db, actor, matter):
    access(actor, matter, {R.ROOT_ADMIN, R.SME})
    versions = list(db.scalars(select(m.AgentProfileVersion).where(m.AgentProfileVersion.matter_id == matter).order_by(m.AgentProfileVersion.created_at.desc(), m.AgentProfileVersion.id).limit(501)))
    if len(versions) > 500: raise HTTPException(413, 'Narrow agent profile history; local limit is 500 revisions')
    return [output(db, actor, item) for item in versions]


def add_version(db, actor, profile, payload):
    old = db.scalar(select(m.AgentProfileVersion).where(m.AgentProfileVersion.created_by == actor.id, m.AgentProfileVersion.request_key == payload.request_key))
    fingerprint = digest(canonical(payload.model_dump(mode='json')).encode())
    if old:
        if old.profile_id != profile.id or old.input_hash != fingerprint: raise HTTPException(409, 'Agent request key changed')
        return old
    previous = db.scalar(select(m.AgentProfileVersion).where(m.AgentProfileVersion.profile_id == profile.id).order_by(m.AgentProfileVersion.revision.desc()).limit(1))
    if previous and payload.expected_version_hash != previous.content_hash: raise HTTPException(409, 'Agent draft history changed; refresh before appending')
    published = [item for item in db.scalars(select(m.AgentProfileVersion).where(m.AgentProfileVersion.profile_id == profile.id).order_by(m.AgentProfileVersion.revision.desc())) if 'publish' in event_map(db, item)]
    active = [item for item in published if state(db, item) == 'published']
    if len(active) > 1: raise HTTPException(409, 'Agent publication chain indeterminate')
    row = m.AgentProfileVersion(matter_id=profile.matter_id, profile_id=profile.id,
        revision=previous.revision + 1 if previous else 1, previous_id=previous.id if previous else None,
        base_published_id=active[0].id if active else published[0].id if published else None, definition_json=canonical(payload.definition.model_dump(mode='json')),
        rationale=payload.rationale, created_by=actor.id, request_key=payload.request_key, input_hash=fingerprint, created_at=clock(), content_hash='')
    row.content_hash = digest(canonical({'profile_id': row.profile_id, 'matter_id': row.matter_id, 'revision': row.revision,
        'previous_id': row.previous_id, 'base_published_id': row.base_published_id, 'definition': payload.definition.model_dump(mode='json'),
        'rationale': row.rationale, 'created_by': row.created_by}).encode())
    db.add(row); db.flush()
    return row


def create(db, actor, payload):
    access(actor, payload.matter_id, {R.ROOT_ADMIN}); lifecycle.mutable(db, payload.matter_id)
    db.scalar(select(m.Matter).where(m.Matter.id == payload.matter_id).with_for_update())
    replay = db.scalar(select(m.AgentProfileVersion).where(m.AgentProfileVersion.created_by == actor.id, m.AgentProfileVersion.request_key == payload.request_key))
    if replay:
        if replay.input_hash != digest(canonical(payload.model_dump(mode='json')).encode()): raise HTTPException(409, 'Agent request key changed')
        return output(db, actor, replay)
    if db.scalar(select(m.AgentProfile.id).where(m.AgentProfile.matter_id == payload.matter_id, m.AgentProfile.name == payload.name)):
        raise HTTPException(409, 'Agent profile name exists; append a new revision')
    profile = m.AgentProfile(matter_id=payload.matter_id, name=payload.name, created_by=actor.id, created_at=clock())
    db.add(profile); db.flush(); version = add_version(db, actor, profile, payload)
    audit(db, 'agent_profile.draft', 'created', actor.id, category='legal_sme', matter_id=profile.matter_id, object_id=version.id)
    result = output(db, actor, version); db.commit(); return result


def append(db, actor, profile_id, payload):
    profile = db.get(m.AgentProfile, profile_id)
    if profile is None: raise HTTPException(404, 'Agent profile unavailable')
    access(actor, profile.matter_id, {R.ROOT_ADMIN}); lifecycle.mutable(db, profile.matter_id)
    db.scalar(select(m.Matter).where(m.Matter.id == profile.matter_id).with_for_update())
    version = add_version(db, actor, profile, payload)
    audit(db, 'agent_profile.revision', 'created', actor.id, category='legal_sme', matter_id=profile.matter_id, object_id=version.id)
    result = output(db, actor, version); db.commit(); return result


def static_test(definition):
    # Deterministic security/configuration checks only; not legal/model evaluation.
    Definition.model_validate(definition.model_dump(mode='json'))
    return {'schema': 'agent-manifest-validation-1', 'passed': True,
        'checks': ['known_agent', 'known_provider_model', 'known_tools_only', 'bounded_timeout', 'bounded_run_budget', 'typed_output'],
        'coverage': 'Static configuration/security validation. No model call, legal accuracy claim, provider approval or automatic publication.'}


def transition(db, actor, version_id, payload):
    version = db.get(m.AgentProfileVersion, version_id)
    if version is None: raise HTTPException(404, 'Agent version unavailable')
    access(actor, version.matter_id, {R.ROOT_ADMIN, R.SME})
    db.scalar(select(m.Matter).where(m.Matter.id == version.matter_id).with_for_update())
    definition = checked(db, version); operations = event_map(db, version); operation = payload.operation
    if payload.content_hash != version.content_hash: raise HTTPException(409, 'Exact agent version hash required')
    if operation in operations or 'archive' in operations: raise HTTPException(409, 'Agent transition already recorded or archived')
    if operation != 'archive': lifecycle.mutable(db, version.matter_id)
    if operation in {'test', 'submit'}:
        access(actor, version.matter_id, {R.ROOT_ADMIN})
        if actor.id != version.created_by or {'submit', 'approve', 'reject', 'publish'} & operations.keys(): raise HTTPException(403, 'Current draft author action required')
        if operation == 'submit' and 'test' not in operations: raise HTTPException(409, 'Test this exact version before submission')
    elif operation in {'approve', 'reject'}:
        access(actor, version.matter_id, {R.SME})
        if actor.id == version.created_by: raise HTTPException(403, 'Independent legal agent reviewer required')
        if 'submit' not in operations or {'approve', 'reject', 'publish'} & operations.keys(): raise HTTPException(409, 'Undecided submitted version required')
        if operation == 'approve' and not payload.content_reviewed: raise HTTPException(422, 'Explicit review of exact prompt, model, tools, limits and test evidence required')
    elif operation == 'publish':
        access(actor, version.matter_id, {R.ROOT_ADMIN})
        if 'approve' not in operations or 'reject' in operations: raise HTTPException(409, 'Exact independently approved version required')
        approver = actor_for(db, operations['approve'].actor_id); access(approver, version.matter_id, {R.SME})
        if approver.id == version.created_by: raise HTTPException(403, 'Independent current legal approver required')
        prior_publications = [item for item in db.scalars(select(m.AgentProfileVersion).where(m.AgentProfileVersion.profile_id == version.profile_id).order_by(m.AgentProfileVersion.revision.desc())) if item.id != version.id and 'publish' in event_map(db, item)]
        if prior_publications and version.base_published_id != prior_publications[0].id:
            raise HTTPException(409, 'Agent publication base changed; append against the current chain')
        if version.base_published_id:
            base = db.get(m.AgentProfileVersion, version.base_published_id); checked(db, base)
            if 'publish' not in event_map(db, base) or db.scalar(select(m.AgentProfileReplacement.id).where(m.AgentProfileReplacement.old_version_id == base.id)):
                raise HTTPException(409, 'Retained unreplaced published base required')
            if base.profile_id != version.profile_id: raise HTTPException(409, 'Same-profile replacement required')
            if checked(db, base).model_dump() == definition.model_dump(): raise HTTPException(409, 'Definition unchanged; retain the published version')
    else:
        access(actor, version.matter_id, {R.ROOT_ADMIN})
    event = m.AgentProfileEvent(matter_id=version.matter_id, version_id=version.id, operation=operation,
        actor_id=actor.id, content_hash=version.content_hash, rationale=payload.rationale,
        report_json=canonical(static_test(definition)) if operation == 'test' else '{}', created_at=clock())
    db.add(event); db.flush()
    if operation == 'publish' and version.base_published_id:
        replacement = m.AgentProfileReplacement(matter_id=version.matter_id, old_version_id=version.base_published_id,
            new_version_id=version.id, actor_id=actor.id, created_at=clock())
        db.add(replacement); db.flush(); create_impacts(db, replacement, actor)
    audit(db, 'agent_profile.' + operation, 'recorded', actor.id, category='legal_sme', matter_id=version.matter_id, object_id=version.id)
    result = output(db, actor, version); db.commit(); return result


def impact_items(db, impact):
    return list(db.scalars(select(m.AgentProfileImpactItem).where(m.AgentProfileImpactItem.impact_id == impact.id).order_by(m.AgentProfileImpactItem.source_id)))


def impact_access(db, actor, impact):
    w.legal(actor, impact.matter_id)
    items = impact_items(db, impact)
    if not items: raise HTTPException(403, 'Source-bound impact provenance unavailable')
    for item in items: rw.retained(db, actor, item)
    return items


def current_impact(db, actor, impact):
    items = impact_access(db, actor, impact)
    replacement = db.get(m.AgentProfileReplacement, impact.replacement_id)
    target = db.get(m.AgentProfileVersion, replacement.new_version_id)
    eligible_version(db, target)
    run = db.get(m.DDRRun, impact.run_id)
    from kestrel.services.ddr_evidence import validate
    validate(db, actor, json.loads(run.snapshot_json))
    frozen = json.loads(impact.snapshot_json)
    if digest(canonical(frozen).encode()) != impact.snapshot_hash or run.snapshot_hash != frozen['run_snapshot_hash'] or target.content_hash != frozen['target_hash']:
        raise HTTPException(409, 'Agent impact snapshot changed')
    for item in items:
        source = db.get(m.SourceVersion, item.source_id)
        if w.snapshot(db, db.get(m.DocumentPolicyVersion, source.policy_id)) != item.source_snapshot:
            raise HTTPException(409, 'Agent impact source attributes changed')
    return run, target, items


def create_impacts(db, replacement, publisher):
    old = db.get(m.AgentProfileVersion, replacement.old_version_id)
    target = db.get(m.AgentProfileVersion, replacement.new_version_id)
    affected = [run for run in db.scalars(select(m.DDRRun).where(m.DDRRun.matter_id == replacement.matter_id))
                if old.id in json.loads(run.config_json).get('agent_profile_ids', [])]
    if len(affected) > 500: raise HTTPException(413, 'Agent impact exceeds the local 500-run publication bound')
    for run in affected:
        evidence = list(db.scalars(select(m.DDREvidence).where(m.DDREvidence.run_id == run.id)))
        if not evidence: raise HTTPException(409, 'Retained DDR evidence required before profile replacement')
        frozen = {'schema': 'agent-profile-impact-1', 'run_id': run.id, 'run_snapshot_hash': run.snapshot_hash,
            'run_config_hash': run.config_hash, 'from_id': old.id, 'from_hash': old.content_hash,
            'target_id': target.id, 'target_hash': target.content_hash,
            'evidence': sorted([{'source_id': e.source_id, 'finding_id': e.finding_id, 'revision_id': e.revision_id,
                'descriptor_hash': e.descriptor_hash} for e in evidence], key=canonical)}
        impact = m.AgentProfileImpact(matter_id=run.matter_id, replacement_id=replacement.id, run_id=run.id,
            snapshot_json=canonical(frozen), snapshot_hash=digest(canonical(frozen).encode()),
            diff_json=canonical(diff(json.loads(old.definition_json), json.loads(target.definition_json))), created_by=publisher.id, created_at=clock())
        db.add(impact); db.flush()
        captured = {}
        for evidence_item in evidence:
            source = db.get(m.SourceVersion, evidence_item.source_id); policy = db.get(m.DocumentPolicyVersion, source.policy_id)
            # The union is enforced by one retained row per source. An old clean
            # classification cannot be relaxed by a later ordinary projection.
            prior = captured.get(source.id)
            classification = evidence_item.retained_classification
            scope = evidence_item.retained_scope
            if prior and (prior.retained_classification != classification or prior.retained_scope != scope):
                raise HTTPException(409, 'Indeterminate retained DDR source restrictions')
            if not prior:
                row = m.AgentProfileImpactItem(matter_id=run.matter_id, source_id=source.id,
                    retained_classification=classification, retained_scope=scope, impact_id=impact.id, run_id=run.id,
                    source_snapshot=w.snapshot(db, policy)); db.add(row); captured[source.id] = row
        db.flush()
        recipients = []
        for account in db.scalars(select(m.Account).where(m.Account.active == True).order_by(m.Account.id)):
            if account.id in {target.created_by, publisher.id, run.requested_by}: continue
            reviewer = principal(db, account, clock())
            if R.SME not in reviewer.roles: continue
            try: impact_access(db, reviewer, impact); recipients.append(account.id)
            except HTTPException as error:
                if error.status_code not in {403, 404, 409}: raise
        urgent = bool(db.scalar(select(m.DDRReportLink.id).where(m.DDRReportLink.run_id == run.id)))
        task = m.AgentProfileImpactTask(matter_id=run.matter_id, impact_id=impact.id,
            assigned_json=canonical(recipients), priority='urgent' if urgent else 'normal',
            due_at=clock() + (86400 if urgent else 3 * 86400), created_at=clock())
        db.add(task); db.flush()
        for account_id in recipients: db.add(m.AgentProfileImpactNotification(matter_id=run.matter_id,
            task_id=task.id, account_id=account_id, created_at=clock()))
        record_impact(db, publisher.id, impact, 'agent_profile.impact', task.id)


def record_impact(db, actor_id, impact, action, object_id):
    from types import SimpleNamespace
    for item in impact_items(db, impact):
        source = db.get(m.SourceVersion, item.source_id); policy = db.get(m.DocumentPolicyVersion, source.policy_id)
        rw.audit_work(db, SimpleNamespace(id=actor_id), policy, action, type('ImpactReference', (), {
            'id': object_id, 'retained_classification': item.retained_classification, 'retained_scope': item.retained_scope})())


def impact_state(db, task):
    operations = {row.operation for row in db.scalars(select(m.AgentProfileImpactDecision).where(m.AgentProfileImpactDecision.task_id == task.id))}
    return 'revoked' if 'revoke' in operations else 'rejected' if 'reject' in operations else 'approved' if 'approve' in operations else 'awaiting_sme'


def task_read(db, actor, task_id):
    task = db.get(m.AgentProfileImpactTask, task_id)
    if task is None: raise HTTPException(404, 'Agent impact task unavailable')
    access(actor, task.matter_id, {R.SME})
    if actor.id not in json.loads(task.assigned_json): raise HTTPException(403, 'Named independent impact reviewer required')
    impact = db.get(m.AgentProfileImpact, task.impact_id); impact_access(db, actor, impact)
    return task, impact


def impact_output(db, actor, task):
    task, impact = task_read(db, actor, task.id)
    replacement = db.get(m.AgentProfileReplacement, impact.replacement_id)
    target = db.get(m.AgentProfileVersion, replacement.new_version_id)
    notification = db.scalar(select(m.AgentProfileImpactNotification).where(m.AgentProfileImpactNotification.task_id == task.id, m.AgentProfileImpactNotification.account_id == actor.id))
    stale = False
    try: current_impact(db, actor, impact)
    except HTTPException as error:
        if error.status_code not in {403, 404, 409}: raise
        stale = True
    return {'id': task.id, 'impact_id': impact.id, 'run_id': impact.run_id, 'matter_id': impact.matter_id,
        'snapshot_hash': impact.snapshot_hash, 'target_id': target.id, 'target_hash': target.content_hash,
        'state': impact_state(db, task), 'stale': stale, 'priority': task.priority, 'due_at': task.due_at,
        'diff': json.loads(impact.diff_json), 'source_ids': [item.source_id for item in impact_items(db, impact)],
        'notification': {'read': bool(notification and notification.read_at), 'acknowledged': bool(notification and notification.acknowledged_at)},
        'notice': 'Reading or acknowledging is not approval. No rerun or publication is queued by this task.'}


def impacts(db, actor, matter):
    access(actor, matter, {R.SME})
    result = []
    for task in db.scalars(select(m.AgentProfileImpactTask).where(m.AgentProfileImpactTask.matter_id == matter).order_by(m.AgentProfileImpactTask.created_at.desc()).limit(501)):
        try: result.append(impact_output(db, actor, task))
        except HTTPException as error:
            if error.status_code not in {403, 404}: raise
    if len(result) > 100: raise HTTPException(413, 'Narrow the agent impact inbox; permitted task limit is 100')
    return result


def notify(db, actor, task_id, payload):
    task, impact = task_read(db, actor, task_id)
    row = db.scalar(select(m.AgentProfileImpactNotification).where(m.AgentProfileImpactNotification.task_id == task.id, m.AgentProfileImpactNotification.account_id == actor.id))
    if row is None: raise HTTPException(403, 'Own notification required')
    if row.read_at is None: row.read_at = clock()
    if payload.operation == 'acknowledge' and row.acknowledged_at is None: row.acknowledged_at = clock()
    record_impact(db, actor.id, impact, 'agent_profile.notification.' + payload.operation, row.id)
    result = impact_output(db, actor, task); db.commit(); return result


def decide_impact(db, actor, task_id, payload):
    task, impact = task_read(db, actor, task_id)
    db.scalar(select(m.Matter).where(m.Matter.id == task.matter_id).with_for_update())
    replacement = db.get(m.AgentProfileReplacement, impact.replacement_id); target = db.get(m.AgentProfileVersion, replacement.new_version_id)
    if payload.snapshot_hash != impact.snapshot_hash or payload.target_hash != target.content_hash: raise HTTPException(409, 'Exact frozen impact and target hashes required')
    prior = impact_state(db, task)
    if prior in {'revoked', 'rejected'} or payload.operation in {'approve','reject'} and prior != 'awaiting_sme': raise HTTPException(409, 'Impact decision already closed')
    if payload.operation != 'revoke':
        lifecycle.mutable(db, task.matter_id); run, target, _ = current_impact(db, actor, impact)
        if actor.id in {target.created_by, impact.created_by, run.requested_by}: raise HTTPException(403, 'Independent impact reviewer required')
    row = m.AgentProfileImpactDecision(matter_id=task.matter_id, task_id=task.id, actor_id=actor.id,
        operation=payload.operation, snapshot_hash=impact.snapshot_hash, target_hash=target.content_hash,
        rationale=payload.rationale, created_at=clock()); db.add(row); db.flush()
    record_impact(db, actor.id, impact, 'agent_profile.impact.' + payload.operation, row.id)
    result = impact_output(db, actor, task); db.commit(); return result


def authorize_rerun(db, actor, task_id):
    task, impact = task_read(db, actor, task_id)
    if impact_state(db, task) != 'approved': raise HTTPException(403, 'Explicit current SME rerun authorization required')
    run, target, _ = current_impact(db, actor, impact)
    decision = db.scalar(select(m.AgentProfileImpactDecision).where(m.AgentProfileImpactDecision.task_id == task.id, m.AgentProfileImpactDecision.operation == 'approve'))
    reviewer = actor_for(db, decision.actor_id)
    task_read(db, reviewer, task.id)
    if reviewer.id in {target.created_by, impact.created_by, run.requested_by}: raise HTTPException(403, 'Independent current rerun approver required')
    config = json.loads(run.config_json); replacement = db.get(m.AgentProfileReplacement, impact.replacement_id)
    ids = [target.id if key == replacement.old_version_id else key for key in config.get('agent_profile_ids', [])]
    resolved = resolve_versions(db, actor, ids)
    material = {'task_id': task.id, 'decision_id': decision.id, 'original_run_id': run.id,
        'snapshot_hash': impact.snapshot_hash, 'target_hash': target.content_hash, 'agent_profile_ids': resolved['agent_profile_ids'],
        'finding_ids': [item['finding_id'] for item in json.loads(run.snapshot_json)['items']]}
    return {**material, 'authorization_hash': digest(canonical(material).encode()),
        'notice': 'Server-side revalidation contract only. No job has been created; never accept this JSON as a client grant.'}


def audit_records(db, object_id):
    item = db.get(m.AgentProfileImpactItem, object_id)
    if item: return impact_items(db, db.get(m.AgentProfileImpact, item.impact_id))
    impact = db.get(m.AgentProfileImpact, object_id)
    if not impact:
        for model in [m.AgentProfileImpactTask, m.AgentProfileImpactDecision, m.AgentProfileImpactNotification]:
            row = db.get(model, object_id)
            if row:
                task = row if model is m.AgentProfileImpactTask else db.get(m.AgentProfileImpactTask, row.task_id)
                impact = db.get(m.AgentProfileImpact, task.impact_id); break
    return impact_items(db, impact) if impact else []
