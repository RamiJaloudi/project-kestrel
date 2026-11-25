import pytest
from kestrel.domain import (
    Organization as O, Role as R, Principal, Document, ReleasedArtifact,
    ImpactSnapshot, can_view_original, can_view_released,
    can_approve_legal_playbook, decide_reanalysis, AccessDenied, StaleImpactError)

MATTER='KESTREL'; CT='KESTREL-CUSTOMER-PRICING'
def user(uid,org,roles,matters=frozenset([MATTER]),walls=frozenset(),ct=frozenset()):
    return Principal(uid,org,frozenset(roles),matters,walls,ct)

def snapshot():
    return ImpactSnapshot('IA-SYNTH-001',MATTER,'1.2','1.3',('DOC-001:v1','DOC-003:v1'),('FND-001',),('REL-001',),('DOC-003:v1',))

def test_allowed_internal_lawyer():
    assert can_view_original(user('a',O.FIRM,[R.LAWYER]),Document('d',MATTER))

def test_root_admin_has_no_blanket_content_access():
    assert not can_view_original(user('root',O.FIRM,[R.ROOT_ADMIN]),Document('d',MATTER))

def test_walled_lawyer_denied():
    assert not can_view_original(user('a',O.FIRM,[R.LAWYER],walls=frozenset([MATTER])),Document('d',MATTER))

def test_wrong_matter_denied():
    assert not can_view_original(user('a',O.FIRM,[R.LAWYER]),Document('d','OTHER'))

def test_firm_non_clean_team_denied():
    d=Document('pricing',MATTER,'clean_team_customer_pricing',CT)
    assert not can_view_original(user('a',O.FIRM,[R.LAWYER]),d)

def test_named_clean_team_firm_allowed():
    d=Document('pricing',MATTER,'clean_team_customer_pricing',CT)
    assert can_view_original(user('a',O.FIRM,[R.LAWYER],ct=frozenset([CT])),d)

def test_external_cannot_view_raw_sources():
    for org,role in [(O.CLIENT,R.CLIENT),(O.BANK,R.BANK)]:
        assert not can_view_original(user('x',org,[role]),Document('d',MATTER))

def test_unreleased_denied_client():
    a=ReleasedArtifact('r',MATTER,frozenset([O.CLIENT]),True,False)
    assert not can_view_released(user('h',O.CLIENT,[R.CLIENT]),a)

def test_unreviewed_denied_client():
    a=ReleasedArtifact('r',MATTER,frozenset([O.CLIENT]),False,True)
    assert not can_view_released(user('h',O.CLIENT,[R.CLIENT]),a)

def test_bank_cannot_view_legal_advice():
    a=ReleasedArtifact('r',MATTER,frozenset([O.BANK]),True,True,privileged=True)
    assert not can_view_released(user('b',O.BANK,[R.BANK]),a)

def test_client_can_view_approved_client_release():
    a=ReleasedArtifact('r',MATTER,frozenset([O.CLIENT]),True,True)
    assert can_view_released(user('h',O.CLIENT,[R.CLIENT]),a)

def test_clean_team_release_needs_antitrust_approval():
    a=ReleasedArtifact('r',MATTER,frozenset([O.BANK]),True,True,
                       clean_team_derived=True,sanitized=True,approved_by_antitrust=False)
    assert not can_view_released(user('b',O.BANK,[R.BANK]),a)

def test_clean_team_release_needs_sanitization():
    a=ReleasedArtifact('r',MATTER,frozenset([O.BANK]),True,True,
                       clean_team_derived=True,sanitized=False,approved_by_antitrust=True)
    assert not can_view_released(user('b',O.BANK,[R.BANK]),a)

def test_self_legal_approval_denied():
    assert not can_approve_legal_playbook(user('editor',O.FIRM,[R.SME]),'editor',MATTER)

def test_independent_legal_approval_allowed():
    assert can_approve_legal_playbook(user('sme',O.FIRM,[R.SME]),'editor',MATTER)

def test_root_admin_not_sme():
    assert not can_approve_legal_playbook(user('root',O.FIRM,[R.ROOT_ADMIN]),'editor',MATTER)

def test_snapshot_counts_from_data():
    assert snapshot().counts()=={'affected_document_versions':2,'approved_findings':1,'released_artifacts':1,'clean_team_document_versions':1}

def test_snapshot_digest_stable_order():
    a=snapshot()
    b=ImpactSnapshot(a.id,a.matter,a.source_playbook,a.target_playbook,tuple(reversed(a.document_version_ids)),a.approved_finding_ids,a.released_artifact_ids,a.clean_team_document_version_ids)
    assert a.digest()==b.digest()

def test_reanalysis_requires_rationale():
    s=snapshot()
    with pytest.raises(ValueError):
        decide_reanalysis(actor=user('sme',O.FIRM,[R.SME]),playbook_author_id='editor',impact=s,supplied_digest=s.digest(),request_id='req',outcome='approve',rationale='  ')

def test_rerun_rejects_stale_impact():
    s=snapshot()
    with pytest.raises(StaleImpactError):
        decide_reanalysis(actor=user('sme',O.FIRM,[R.SME]),playbook_author_id='editor',impact=s,supplied_digest='bad',request_id='req',outcome='approve',rationale='material')

def test_rerun_denies_author():
    s=snapshot()
    with pytest.raises(AccessDenied):
        decide_reanalysis(actor=user('sme',O.FIRM,[R.SME]),playbook_author_id='sme',impact=s,supplied_digest=s.digest(),request_id='req',outcome='approve',rationale='material')

def test_rerun_denies_root_admin():
    s=snapshot()
    with pytest.raises(AccessDenied):
        decide_reanalysis(actor=user('root',O.FIRM,[R.ROOT_ADMIN]),playbook_author_id='editor',impact=s,supplied_digest=s.digest(),request_id='req',outcome='approve',rationale='material')

def test_rerun_denies_walled_sme():
    s=snapshot()
    with pytest.raises(AccessDenied):
        decide_reanalysis(actor=user('sme',O.FIRM,[R.SME],walls=frozenset([MATTER])),playbook_author_id='editor',impact=s,supplied_digest=s.digest(),request_id='req',outcome='approve',rationale='material')

def test_rerun_restricts_clean_team_scope():
    s=snapshot()
    with pytest.raises(AccessDenied):
        decide_reanalysis(actor=user('sme',O.FIRM,[R.SME]),playbook_author_id='editor',impact=s,supplied_digest=s.digest(),request_id='req',outcome='approve',rationale='material',scope='all_including_clean_team')

def test_rerun_approved_for_authorized_sme():
    s=snapshot()
    d=decide_reanalysis(actor=user('sme',O.FIRM,[R.SME]),playbook_author_id='editor',impact=s,supplied_digest=s.digest(),request_id='req',outcome='approve',rationale='The new rule affects indirect control clauses.')
    assert d.outcome=='approve' and d.impact_digest==s.digest()

def test_rejection_is_not_an_approval():
    s=snapshot()
    d=decide_reanalysis(actor=user('sme',O.FIRM,[R.SME]),playbook_author_id='editor',impact=s,supplied_digest=s.digest(),request_id='req',outcome='reject',rationale='Needs narrower scope')
    assert d.outcome=='reject'


def test_exact_rule_field_diff_and_added_rule():
    from kestrel.domain import compare_playbook_rules
    old=[{"rule_id":"COC-03", "trigger":"direct"}]
    new=[{"rule_id":"COC-03", "trigger":"direct and indirect"},
         {"rule_id":"COC-09", "trigger":"deemed assignment"}]
    changes=compare_playbook_rules(old,new)
    assert changes[0]["rule_id"]=="COC-03" and changes[0]["field"]=="trigger"
    assert changes[0]["old"]=="direct"
    assert changes[1]["rule_id"]=="COC-09" and changes[1]["change"]=="added"

def test_notification_read_not_task_approval():
    from kestrel.domain import Notification
    note=Notification("N-1", "sme-1")
    assert note.mark_read().state=="read"
    assert note.acknowledge().state=="acknowledged"
    assert note.mark_read().task_state=="awaiting_decision"

def test_impact_digest_changes_on_diff_hash():
    from dataclasses import replace
    a=snapshot()
    assert a.digest()!=replace(a,diff_hash="new-material-rule").digest()
