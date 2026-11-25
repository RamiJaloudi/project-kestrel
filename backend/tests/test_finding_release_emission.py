"""Independent containment of legacy finding-derived audience artifacts.

Only disposable fixture construction temporarily disables the new pure guard.
Every assertion of an emission/decision runs after that helper is restored.
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from test_auth_policy import env, login
from test_diligence import D, assessment
from test_disclosures import D as DISCLOSURES, prepared
from test_document_workflow import BASE, allow_processing
from test_finding_data_tables import membership, ordinary_source, signed
from test_observability_governance import post
from test_reports import R, generate
from test_table_security_review import confirmed

C = '/api/v1/collaboration'
Q = '/api/v1/questions'
CANARY = 'RETAINED_EMISSION_PRIVATE_CANARY'


def external_login(client, audience):
    name, origin = ('client', 'https://client.localhost') if audience == 'halden' else ('bank', 'https://bank.localhost')
    response = login(client, name, origin=origin)
    assert response.status_code == 200, response.text
    return {'origin': origin, 'x-csrf-token': response.json()['csrf_token']}


def origin(audience):
    return 'https://client.localhost' if audience == 'halden' else 'https://bank.localhost'


def denied(response):
    assert response.status_code in {403, 409}, response.text
    assert CANARY not in response.text
    assert 'content-disposition' not in response.headers


def retained_receipt(sessions, report):
    """Compare original artifact/approval bytes and hashes, excluding access audits."""
    from kestrel import models as m
    from kestrel.services import workflow
    def values(row):
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}
    with sessions() as db:
        release = db.get(m.ReleasePackage, report['release_id'])
        root = db.get(m.DocumentPolicyVersion, release.policy_id)
        keys = [ref['finding_id'] for ref in json.loads(release.references_json)]
        history = list(db.scalars(select(m.LegalFindingRevision).where(
            m.LegalFindingRevision.record_key.in_(keys),
        ).order_by(m.LegalFindingRevision.id)))
        policies = {policy.id: policy for policy in workflow.lineage(db, root)}
        for row in history:
            for policy in workflow.lineage(db, db.get(m.DocumentPolicyVersion, row.policy_id)):
                policies[policy.id] = policy
        return {
            'release': values(release),
            'policy': values(root), 'computed_snapshot': workflow.snapshot(db, root),
            'retained_history': [values(row) for row in history],
            'retained_policies': [values(policies[key]) for key in sorted(policies)],
            'lineage_edges': [values(row) for row in db.scalars(select(m.PolicySource).where(
                m.PolicySource.artifact_id.in_(policies),
            ).order_by(m.PolicySource.id))],
            'report': values(db.get(m.ReportVersion, report['id'])),
            'approvals': [values(row) for row in db.scalars(select(m.ReleaseApproval).where(
                m.ReleaseApproval.release_id == release.id,
            ).order_by(m.ReleaseApproval.id))],
        }


def restricted_correction(env):
    http, sessions, ids, _ = env
    allow_processing(http, sessions, ids)
    membership(sessions, ids)
    membership(sessions, ids, 'sme')
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'], classification='clean_team', clean_team_scope='pricing')
    response = post(http, D + '/findings', csrf, assessment(source, summary=CANARY + ' requires a pricing consent review.'))
    assert response.status_code == 201, response.text
    finding = response.json()
    ordinary_source(sessions, source)
    response = post(http, D + '/findings/' + finding['id'] + '/revisions', csrf,
                    assessment(source, expected_revision=1, summary=CANARY + ' still requires a pricing consent review.'))
    assert response.status_code == 201, response.text
    finding = response.json()
    return source, finding, csrf


def legacy_artifact(env, monkeypatch, audience='halden', *, approved=True):
    """Build an already-existing vulnerable artifact through normal isolated APIs."""
    from kestrel import models as m
    from kestrel.services import finding_release_guard
    http, sessions, ids, app = env
    source, finding, csrf = restricted_correction(env)

    original_guard = finding_release_guard.denial
    answer_id = reply_id = None
    with monkeypatch.context() as legacy_only:
        legacy_only.setattr(finding_release_guard, 'denial', lambda *args, **kwargs: None)
        response = post(http, R + '/generate', csrf, {
            'matter_id': ids['matter'], 'audience': audience, 'kind': 'board_pack',
            'title': CANARY + ' legacy reviewed report', 'finding_ids': [finding['id']],
        })
        assert response.status_code == 201, response.text
        report = response.json()
        if approved:
            csrf = signed(http, 'sme')
            response = post(http, BASE + '/releases/' + report['release_id'] + '/approve', csrf, {
                'content_hash': report['content_hash'], 'snapshot_hash': report['snapshot_hash'],
                'rationale': 'Isolated legacy legal approval predating retained-finding containment, without antitrust.',
            })
            assert response.status_code == 200, response.text
            with TestClient(app, base_url=origin(audience)) as client:
                headers = external_login(client, audience)
                response = client.get(BASE + '/releases/' + report['release_id'])
                assert response.status_code == 200 and CANARY in response.text, response.text
                response = client.post(Q, json={
                    'matter_id': ids['matter'], 'question': 'Which pricing consent review is required?', 'mode': 'lexical',
                }, headers=headers)
                assert response.status_code == 201 and CANARY in response.text, response.text
                answer_id = response.json()['id']
                response = client.post(C, json={
                    'release_id': report['release_id'], 'body': CANARY + ' audience question about consent.',
                }, headers=headers)
                assert response.status_code == 201, response.text
                question_id = response.json()['id']
                csrf = signed(http)
                response = post(http, C, csrf, {
                    'release_id': report['release_id'], 'parent_id': question_id, 'kind': 'reply',
                    'body': CANARY + ' firm reply about the exact consent requirement.',
                })
                assert response.status_code == 201, response.text
                reply = response.json()
                reply_id = reply['id']
                csrf = signed(http, 'sme')
                response = post(http, C + '/' + reply_id + '/approve', csrf, {
                    'body_hash': reply['body_hash'], 'rationale': 'Isolated legacy audience reply approval without antitrust.',
                })
                assert response.status_code == 200, response.text
                response = client.get(C, params={'release_id': report['release_id']})
                assert response.status_code == 200 and CANARY in response.text, response.text
    assert finding_release_guard.denial is original_guard
    with sessions() as db:
        policy_id = db.get(m.ReleasePackage, report['release_id']).policy_id
    return {
        'source': source, 'finding': finding, 'report': report, 'policy_id': policy_id,
        'answer_id': answer_id, 'reply_id': reply_id, 'receipt': retained_receipt(sessions, report),
    }


@pytest.mark.parametrize('kind', ['package', 'report'])
def test_new_unbound_derivative_is_rejected_before_persisting_any_draft(env, kind):
    from kestrel import models as m
    http, sessions, ids, _ = env
    _, finding, csrf = restricted_correction(env)
    def counts():
        with sessions() as db:
            return tuple(db.scalar(select(func.count()).select_from(model)) for model in [
                m.ReleasePackage, m.ReportVersion, m.DocumentPolicyVersion, m.PolicySource,
            ])
    before = counts()
    if kind == 'report':
        response = generate(http, csrf, ids['matter'], finding['id'])
    else:
        response = post(http, BASE + '/releases', csrf, {
            'matter_id': ids['matter'], 'audience': 'halden', 'title': 'New unbound finding derivative',
            'summary': CANARY + ' must not persist as an unreadable audience draft.',
            'references': [{'finding_id': finding['id'], 'revision_id': finding['revision_id'],
                            'public_reference': 'Synthetic exact reviewed assessment'}],
        })
    denied(response)
    assert counts() == before


def test_intermediate_finding_policy_restriction_cannot_be_dropped_from_retained_prefix(env):
    from kestrel import models as m
    http, sessions, ids, _ = env
    allow_processing(http, sessions, ids)
    membership(sessions, ids)
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'])
    response = post(http, D + '/findings', csrf, assessment(source))
    assert response.status_code == 201, response.text
    protected = response.json()
    response = post(http, D + '/findings', csrf, assessment(source))
    assert response.status_code == 201, response.text
    first = response.json()
    with sessions() as db:
        protected_policy = db.get(m.DocumentPolicyVersion, db.get(m.LegalFindingRevision, protected['revision_id']).policy_id)
        protected_policy.classification = 'clean_team'
        protected_policy.clean_team_scope = 'pricing'
        first_policy = db.get(m.LegalFindingRevision, first['revision_id']).policy_id
        db.add(m.PolicySource(artifact_id=first_policy, source_id=protected_policy.id))
        db.commit()
    response = post(http, D + '/findings/' + first['id'] + '/revisions', csrf,
                    assessment(source, expected_revision=1, summary=CANARY + ' derives from a restricted intermediate finding.'))
    assert response.status_code == 201, response.text
    current = response.json()
    response = post(http, BASE + '/releases', csrf, {
        'matter_id': ids['matter'], 'audience': 'halden', 'title': 'Unbound intermediate-policy derivative',
        'summary': CANARY + ' must retain the intermediate finding policy restriction.',
        'references': [{'finding_id': current['id'], 'revision_id': current['revision_id'],
                        'public_reference': 'Synthetic reviewed finding with retained lineage'}],
    })
    denied(response)


@pytest.mark.parametrize('change', ['wall', 'session'])
def test_release_approval_rechecks_current_actor_before_committing_decision(env, monkeypatch, change):
    from kestrel import models as m
    from kestrel.services import workflow
    http, sessions, ids, _ = env
    allow_processing(http, sessions, ids)
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'])
    response = post(http, D + '/findings', csrf, assessment(source))
    assert response.status_code == 201, response.text
    response = generate(http, csrf, ids['matter'], response.json()['id'])
    assert response.status_code == 201, response.text
    report = response.json()
    before = retained_receipt(sessions, report)
    csrf = signed(http, 'sme')
    original = workflow.package
    fired = False

    def package_then_revoke(*args, **kwargs):
        nonlocal fired
        result = original(*args, **kwargs)
        if not fired:
            fired = True
            with sessions() as writer:
                if change == 'wall':
                    writer.add(m.EthicalWall(account_id=ids['sme'], matter_id=ids['matter']))
                else:
                    for session in writer.scalars(select(m.ServerSession).where(m.ServerSession.account_id == ids['sme'])):
                        session.revoked = True
                writer.commit()
        return result

    monkeypatch.setattr(workflow, 'package', package_then_revoke)
    response = post(http, BASE + '/releases/' + report['release_id'] + '/approve', csrf, {
        'content_hash': report['content_hash'], 'snapshot_hash': report['snapshot_hash'],
        'rationale': 'A revoked actor cannot commit an audience-publication decision.',
    })
    assert fired
    assert response.status_code in {401, 403, 409}, response.text
    assert retained_receipt(sessions, report) == before


@pytest.mark.parametrize('change', ['wall', 'session'])
def test_opaque_revoke_rechecks_current_actor_before_committing_receipt(env, monkeypatch, change):
    from kestrel import models as m
    from kestrel.services import workflow
    http, sessions, ids, _ = env
    item = legacy_artifact(env, monkeypatch)
    csrf = signed(http, 'sme')
    original = workflow.snapshot
    fired = False

    def snapshot_then_revoke(db, policy):
        nonlocal fired
        result = original(db, policy)
        if policy.id == item['policy_id'] and not fired:
            fired = True
            with sessions() as writer:
                if change == 'wall':
                    writer.add(m.EthicalWall(account_id=ids['sme'], matter_id=ids['matter']))
                else:
                    for session in writer.scalars(select(m.ServerSession).where(m.ServerSession.account_id == ids['sme'])):
                        session.revoked = True
                writer.commit()
        return result

    monkeypatch.setattr(workflow, 'snapshot', snapshot_then_revoke)
    response = post(http, BASE + '/releases/' + item['report']['release_id'] + '/revoke', csrf, {
        'content_hash': item['report']['content_hash'], 'snapshot_hash': item['receipt']['computed_snapshot'],
        'rationale': 'Containment still requires a current authenticated legal actor at commit.',
    })
    assert fired
    assert response.status_code in {401, 403, 409}, response.text
    assert CANARY not in response.text
    assert retained_receipt(sessions, item['report']) == item['receipt']


@pytest.mark.parametrize('actor', ['root', 'client', 'bank', 'otherlawyer'])
def test_opaque_containment_does_not_grant_other_accounts_a_release_control(env, monkeypatch, actor):
    from kestrel import models as m
    from kestrel.bootstrap import provision
    from kestrel.services.auth import clock
    from test_auth_policy import PASSWORD
    http, sessions, ids, app = env
    item = legacy_artifact(env, monkeypatch)
    if actor == 'otherlawyer':
        with sessions() as db:
            account = provision(db, actor, 'firm', ['firm_lawyer'], PASSWORD)
            db.add(m.MatterAssignment(account_id=account.id, matter_id=ids['matter'], expires_at=clock()+3600))
            db.commit()
    body = {'content_hash': item['report']['content_hash'], 'snapshot_hash': item['receipt']['computed_snapshot'],
            'rationale': 'Unrelated accounts cannot operate blind release containment controls.'}
    if actor in {'client', 'bank'}:
        audience = 'halden' if actor == 'client' else 'castlegate'
        with TestClient(app, base_url=origin(audience)) as external:
            headers = external_login(external, audience)
            response = external.post(BASE+'/releases/'+item['report']['release_id']+'/revoke', json=body, headers=headers)
    else:
        csrf = signed(http, actor)
        response = post(http, BASE+'/releases/'+item['report']['release_id']+'/revoke', csrf, body)
    assert response.status_code == 403, response.text
    assert CANARY not in response.text
    assert retained_receipt(sessions, item['report']) == item['receipt']


@pytest.mark.parametrize('field', ['content_hash', 'snapshot_hash'])
def test_opaque_containment_rejects_stale_concurrency_evidence(env, monkeypatch, field):
    http, sessions, _, _ = env
    item = legacy_artifact(env, monkeypatch)
    csrf = signed(http, 'sme')
    body = {'content_hash': item['report']['content_hash'], 'snapshot_hash': item['receipt']['computed_snapshot'],
            'rationale': 'A containment command still requires the correct retained package evidence.'}
    body[field] = '0'*64
    response = post(http, BASE+'/releases/'+item['report']['release_id']+'/revoke', csrf, body)
    assert response.status_code == 409, response.text
    assert CANARY not in response.text
    assert retained_receipt(sessions, item['report']) == item['receipt']


@pytest.mark.parametrize('actor', ['lawyer', 'sme'])
def test_authorized_opaque_containment_returns_only_a_minimal_receipt(env, monkeypatch, actor):
    from kestrel import models as m
    http, sessions, _, _ = env
    item = legacy_artifact(env, monkeypatch)
    csrf = signed(http, actor)
    response = post(http, BASE+'/releases/'+item['report']['release_id']+'/revoke', csrf, {
        'content_hash': item['report']['content_hash'], 'snapshot_hash': item['receipt']['computed_snapshot'],
        'rationale': 'The creator or current scoped SME contains this legacy artifact without reading its body.',
    })
    assert response.status_code == 200, response.text
    assert response.json() == {'id': item['report']['release_id'], 'revoked': True}
    assert CANARY not in response.text
    after = retained_receipt(sessions, item['report'])
    assert after['report'] == item['receipt']['report']
    assert after['release'] == item['receipt']['release']
    assert after['retained_history'] == item['receipt']['retained_history']
    assert all(value in after['approvals'] for value in item['receipt']['approvals'])
    with sessions() as db:
        policy = db.get(m.DocumentPolicyVersion, item['policy_id'])
        assert not policy.released and policy.approved_snapshot_hash is None
        assert db.scalar(select(func.count()).select_from(m.ReleaseApproval).where(
            m.ReleaseApproval.release_id == item['report']['release_id'], m.ReleaseApproval.kind == 'revoke')) == 1


def test_opaque_containment_rechecks_current_sme_role_even_when_legal_role_remains(env, monkeypatch):
    from kestrel import models as m
    from kestrel.services import workflow
    http, sessions, ids, _ = env
    item = legacy_artifact(env, monkeypatch)
    with sessions() as db:
        legal_role = db.scalar(select(m.Role.id).where(m.Role.name == 'firm_lawyer'))
        db.add(m.RoleGrant(account_id=ids['sme'], role_id=legal_role))
        db.commit()
    csrf = signed(http, 'sme')
    original = workflow.snapshot
    fired = False
    def snapshot_then_remove_sme(*args, **kwargs):
        nonlocal fired
        value = original(*args, **kwargs)
        if not fired:
            fired = True
            with sessions() as writer:
                sme_role = writer.scalar(select(m.Role.id).where(m.Role.name == 'legal_sme'))
                grant = writer.scalar(select(m.RoleGrant).where(m.RoleGrant.account_id == ids['sme'], m.RoleGrant.role_id == sme_role))
                writer.delete(grant)
                writer.commit()
        return value
    monkeypatch.setattr(workflow, 'snapshot', snapshot_then_remove_sme)
    response = post(http, BASE+'/releases/'+item['report']['release_id']+'/revoke', csrf, {
        'content_hash': item['report']['content_hash'], 'snapshot_hash': item['receipt']['computed_snapshot'],
        'rationale': 'An unrelated lawyer cannot retain the blind containment power after SME removal.',
    })
    assert fired and response.status_code in {403, 409}, response.text
    assert CANARY not in response.text
    assert retained_receipt(sessions, item['report']) == item['receipt']


@pytest.mark.parametrize('audience', ['halden', 'castlegate'])
def test_legacy_approved_package_direct_list_and_canonical_checker_are_contained_without_rewriting(env, monkeypatch, audience):
    http, sessions, ids, app = env
    item = legacy_artifact(env, monkeypatch, audience)
    with TestClient(app, base_url=origin(audience)) as client:
        headers = external_login(client, audience)
        denied(client.get(BASE + '/releases/' + item['report']['release_id']))
        response = client.get(BASE + '/releases', params={'matter_id': ids['matter']})
        assert response.status_code == 200 and response.json() == [], response.text
        response = client.get(R, params={'matter_id': ids['matter']})
        assert response.status_code == 200 and response.json() == [], response.text
        response = client.post('/api/v1/document-authorizations', json={
            'document_version_id': item['policy_id'], 'action': 'read',
        }, headers=headers)
        assert response.status_code == 200 and response.json()['allowed'] is False, response.text
        assert CANARY not in response.text
    # A Root account does not gain internal legal access to the retained artifact.
    signed(http, 'root')
    denied(http.get(BASE + '/releases/' + item['report']['release_id']))
    assert retained_receipt(sessions, item['report']) == item['receipt']


@pytest.mark.parametrize('audience', ['halden', 'castlegate'])
@pytest.mark.parametrize('format', ['docx', 'pdf', 'xlsx'])
def test_legacy_report_download_cannot_emit_any_format(env, monkeypatch, audience, format):
    from kestrel.adapters import report_export
    _, sessions, _, app = env
    item = legacy_artifact(env, monkeypatch, audience)
    calls = []
    def renderer(*args):
        calls.append(args)
        return b'PRIVATE_RENDER_SENTINEL'
    monkeypatch.setattr(report_export, 'export', renderer)
    with TestClient(app, base_url=origin(audience)) as client:
        external_login(client, audience)
        response = client.get(R + '/' + item['report']['id'] + '/download/' + format)
        denied(response)
        assert b'PRIVATE_RENDER_SENTINEL' not in response.content and calls == []
    assert retained_receipt(sessions, item['report']) == item['receipt']


@pytest.mark.parametrize('audience', ['halden', 'castlegate'])
def test_cached_answers_scope_only_refs_and_fresh_corpus_cannot_reemit_legacy_package(env, monkeypatch, audience):
    from kestrel import models as m
    from kestrel.adapters.extraction import canonical
    from kestrel.services.auth import clock
    _, sessions, ids, app = env
    item = legacy_artifact(env, monkeypatch, audience)
    with sessions() as db:
        old = db.get(m.QuestionAnswer, item['answer_id'])
        value = json.loads(old.result_json)
        refs = [{key: citation[key] for key in ['kind', 'object_id', 'snapshot']} for citation in value['citations']]
        assert refs
        # A stored empty-citation response may still contain private corpus counts.
        value['citations'] = []
        value['_scope_refs'] = refs
        value['answer'] = CANARY + ' retained cached ranking metadata.'
        copy = m.QuestionAnswer(actor_id=old.actor_id, matter_id=old.matter_id,
                                question='Synthetic scope-only cached answer', result_json=canonical(value), created_at=clock())
        db.add(copy)
        db.commit()
        scope_only_id = copy.id
    with TestClient(app, base_url=origin(audience)) as client:
        headers = external_login(client, audience)
        denied(client.get(Q + '/' + item['answer_id']))
        denied(client.get(Q + '/' + scope_only_id))
        response = client.get(Q, params={'matter_id': ids['matter']})
        assert response.status_code == 200 and response.json() == [], response.text
        response = client.post(Q, json={
            'matter_id': ids['matter'], 'question': 'Which pricing consent review is required?', 'mode': 'lexical',
        }, headers=headers)
        assert response.status_code == 201, response.text
        assert response.json()['citations'] == [] and CANARY not in response.text
        assert response.json()['retrieval']['authorized_chunks'] == 0
    assert retained_receipt(sessions, item['report']) == item['receipt']


@pytest.mark.parametrize('audience', ['halden', 'castlegate'])
def test_legacy_collaboration_is_unavailable_after_retained_chain_containment(env, monkeypatch, audience):
    _, sessions, _, app = env
    item = legacy_artifact(env, monkeypatch, audience)
    with TestClient(app, base_url=origin(audience)) as client:
        headers = external_login(client, audience)
        denied(client.get(C, params={'release_id': item['report']['release_id']}))
        denied(client.post(C, json={
            'release_id': item['report']['release_id'], 'kind': 'reply', 'parent_id': item['reply_id'],
            'body': 'This new reply must not extend an unavailable retained package.',
        }, headers=headers))
    assert retained_receipt(sessions, item['report']) == item['receipt']


@pytest.mark.parametrize('audience', ['halden', 'castlegate'])
def test_old_pending_package_cannot_gain_audience_approval_from_incomplete_lineage(env, monkeypatch, audience):
    http, sessions, _, _ = env
    item = legacy_artifact(env, monkeypatch, audience, approved=False)
    csrf = signed(http, 'sme')
    response = post(http, BASE + '/releases/' + item['report']['release_id'] + '/approve', csrf, {
        'content_hash': item['report']['content_hash'], 'snapshot_hash': item['receipt']['computed_snapshot'],
        'rationale': 'Current legal approval cannot silently clear an omitted retained clean-team source.',
    })
    denied(response)
    assert retained_receipt(sessions, item['report']) == item['receipt']


@pytest.mark.parametrize('audience', ['halden', 'castlegate'])
def test_ordinary_corrected_finding_can_still_be_independently_released_without_source_access(env, audience):
    http, _, ids, app = env
    allow_processing(http, env[1], ids)
    csrf = signed(http)
    source = confirmed(http, csrf, ids['matter'])
    response = post(http, D + '/findings', csrf, assessment(source))
    assert response.status_code == 201, response.text
    finding = response.json()
    response = post(http, D + '/findings/' + finding['id'] + '/revisions', csrf,
                    assessment(source, expected_revision=1, summary='Ordinary corrected consent finding remains eligible for independent publication.'))
    assert response.status_code == 201, response.text
    finding = response.json()
    response = generate(http, csrf, ids['matter'], finding['id'], audience)
    assert response.status_code == 201, response.text
    report = response.json()
    csrf = signed(http, 'sme')
    response = post(http, BASE + '/releases/' + report['release_id'] + '/approve', csrf, {
        'content_hash': report['content_hash'], 'snapshot_hash': report['snapshot_hash'],
        'rationale': 'Independent review of a current ordinary correction with no hidden restriction broadening.',
    })
    assert response.status_code == 200, response.text
    with TestClient(app, base_url=origin(audience)) as client:
        external_login(client, audience)
        response = client.get(BASE + '/releases/' + report['release_id'])
        assert response.status_code == 200, response.text
        assert client.get(R, params={'matter_id': ids['matter']}).json()[0]['body'] == report['body']
        assert client.get(BASE + '/documents/' + source['id']).status_code == 403


def test_legitimate_independently_approved_clean_team_transcript_remains_available_without_original(env):
    http, _, _, app = env
    source, _, artifact, _ = prepared(env, clean=True)
    csrf = signed(http, 'sme')
    response = post(http, DISCLOSURES + '/artifacts/' + artifact['id'] + '/decisions', csrf, {
        'operation': 'legal_approve', 'bundle_hash': artifact['bundle_hash'],
        'rationale': 'Independent legal approval of the exact scoped sanitized transcript.',
    })
    assert response.status_code == 200, response.text
    csrf = signed(http, 'antitrust')
    response = post(http, DISCLOSURES + '/artifacts/' + artifact['id'] + '/decisions', csrf, {
        'operation': 'antitrust_approve', 'bundle_hash': artifact['bundle_hash'],
        'rationale': 'Separate independent counsel declassification of the exact sanitized transcript.',
    })
    assert response.status_code == 200, response.text
    with TestClient(app, base_url='https://bank.localhost') as bank:
        external_login(bank, 'castlegate')
        response = bank.get(DISCLOSURES + '/artifacts/' + artifact['id'] + '/reader')
        assert response.status_code == 200, response.text
        assert source['id'] not in response.text and 'prior written consent' not in response.text
        response = bank.get(DISCLOSURES + '/artifacts/' + artifact['id'] + '/download')
        assert response.status_code == 200 and response.content.startswith(b'%PDF'), response.text
        assert bank.get(BASE + '/documents/' + source['id']).status_code == 403
