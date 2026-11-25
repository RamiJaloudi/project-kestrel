"""Canonical document authorization: person walls, document state and lineage.

All production document decisions enter here. Attributes must come from retained
server records; the checker is explanatory and never grants access.
"""
from fastapi import HTTPException
from sqlalchemy import select
from kestrel.domain import Organization as O, Role as R, member_and_not_walled
from kestrel.repositories.identity import clean_scope
from kestrel.services.documents import TYPES, ACTIONS, lineage, snapshot


def evaluate(db, actor, doc, action, now):
    def deny(code): return {"allowed":False,"reason_code":code,"policy_version":"document-abac-1"}
    if action not in ACTIONS: return deny("ACTION_UNKNOWN")
    if doc is None or not member_and_not_walled(actor,doc.matter_id): return deny("ACCESS_DENIED")
    from kestrel.models import MatterLifecycle
    lifecycle=db.get(MatterLifecycle,doc.matter_id)
    if lifecycle and lifecycle.external_closed and actor.org!=O.FIRM:return deny('EXTERNAL_WORKSPACE_CLOSED')
    if lifecycle and lifecycle.frozen and action in {'edit','analyze','share','export'}:return deny('SIGNING_FROZEN')
    if doc.resource_type=='sanitized_document':
        from kestrel.services.disclosures import authorize
        return authorize(db,actor,doc,action,now)
    internal = actor.org == O.FIRM and bool(actor.roles & {R.LAWYER,R.SME,R.ANTITRUST})
    if action=='triage' and not internal:return deny('ACCESS_DENIED')
    try: sources = lineage(db,doc)
    except ValueError: return deny("LINEAGE_INVALID")
    own_upload=False
    if actor.org==O.CLIENT and doc.resource_type=='client_upload' and action in {'read','download'}:
        from kestrel.models import ClientSubmission
        own_upload=db.scalar(select(ClientSubmission.id).where(ClientSubmission.policy_id==doc.id,ClientSubmission.uploaded_by==actor.id,ClientSubmission.data.is_not(None))) is not None
    from kestrel.services.content_labels import guard
    for item in sources:
        if actor.org!=O.FIRM:
            from kestrel.models import SourceVersion
            source=db.scalar(select(SourceVersion).where(SourceVersion.policy_id==item.id))
            if source and source.file_name.lower().endswith(('.xlsx','.xlsm')):
                from kestrel.adapters.workbook_safety import scan
                try:visibility=scan(source)
                except HTTPException:return deny('WORKBOOK_VISIBILITY_REQUIRED')
                if not visibility or not visibility['complete']:return deny('WORKBOOK_VISIBILITY_REQUIRED')
                if visibility['receipt']['sensitive_hidden'] and (item.classification!='clean_team' or not item.clean_team_scope):return deny('WORKBOOK_HANDLING_REQUIRED')
        label_denial=guard(db,actor,item,action,now)
        if label_denial:return deny(label_denial)
        if item.matter_id != doc.matter_id: return deny("LINEAGE_INVALID")
        if item.resource_type not in TYPES or item.classification not in {"ordinary","privileged","clean_team"}: return deny("UNCLASSIFIED")
        if not item.classification_confirmed and action!='triage' and not own_upload: return deny("CLASSIFICATION_PENDING")
        if item.review_state not in {"candidate","reviewed","rejected"}: return deny("STATE_UNKNOWN")
        if item.quarantined: return deny("QUARANTINED")
        if item.superseded and action not in {"historical_read","export_metadata"}: return deny("SUPERSEDED")
        if item.signing_frozen and action in {"edit","analyze","share","export"}: return deny("SIGNING_FROZEN")
        if action == "analyze":
            from kestrel.models import SourceVersion,OCRVerification
            source=db.scalar(select(SourceVersion).where(SourceVersion.policy_id==item.id))
            if source:
                from kestrel.adapters.workbook_safety import processing
                try:processing(source,item)
                except HTTPException:return deny('WORKBOOK_PROCESSING_REQUIRED')
            if source and source.extractor_version.startswith('ocr:'):
                record=db.get(OCRVerification,source.id)
                if not record or record.text_hash!=source.text_hash:return deny('OCR_UNVERIFIED')
        if action == "analyze" and item.ai_restricted: return deny("AI_RESTRICTED")
        if action == "edit" and (item.released or item.review_state == "reviewed"): return deny("NEW_VERSION_REQUIRED")
    if internal:
        for item in sources:
            if item.classification == "clean_team" and (not item.clean_team_scope or not clean_scope(db,actor.id,item.matter_id,item.clean_team_scope,now)):
                return deny("CLEAN_TEAM_REQUIRED")
        if action in {"share","export"}: return deny("APPROVED_PACKAGE_REQUIRED")
    else:
        from kestrel.models import PolicyRecipient
        for item in sources:
            recipients=set(db.scalars(select(PolicyRecipient.account_id).where(PolicyRecipient.policy_id==item.id)))
            if recipients and actor.id not in recipients:return deny('RECIPIENT_EXCLUDED')
        if actor.org not in {O.CLIENT,O.BANK} or action not in {"read","download"}: return deny("ACCESS_DENIED")
        if own_upload:
            if any(p.classification=='clean_team' and not clean_scope(db,actor.id,p.matter_id,p.clean_team_scope or '',now) for p in sources):return deny('CLEAN_TEAM_REQUIRED')
            return {"allowed":True,"reason_code":"OWN_CLIENT_UPLOAD","policy_version":"document-abac-2"}
        # Explicit exception for named, independently approved Halden clean-team source versions.
        # Candidate findings, other source versions and bank users never enter this branch.
        if actor.org==O.CLIENT and doc.classification=='clean_team' and doc.resource_type!='legal_advice' and clean_scope(db,actor.id,doc.matter_id,doc.clean_team_scope or '',now):
            from kestrel.models import SourceAccessGrant,SourceVersion
            source_id=db.scalar(select(SourceVersion.id).where(SourceVersion.policy_id==doc.id))
            approved=db.scalar(select(SourceAccessGrant.id).where(SourceAccessGrant.source_id==source_id,SourceAccessGrant.account_id==actor.id,SourceAccessGrant.state=='approved',SourceAccessGrant.expires_at>now,SourceAccessGrant.snapshot_hash==snapshot(db,doc))) if source_id else None
            if approved and doc.review_state=='reviewed' and not any(p.classification=='privileged' or p.resource_type=='legal_advice' for p in sources):
                return {"allowed":True,"reason_code":"NAMED_SOURCE_GRANT","policy_version":"document-abac-2"}
        if doc.resource_type not in {"finding","report","tracker","export"}: return deny("SOURCE_ACCESS_DENIED")
        if not doc.released or doc.review_state != "reviewed" or doc.audience != actor.org.value: return deny("RELEASE_REQUIRED")
        if any(item.review_state != "reviewed" for item in sources): return deny("REVIEW_REQUIRED")
        if doc.resource_type in {"report","tracker","export"} and len(sources) == 1: return deny("LINEAGE_REQUIRED")
        if doc.classification == "privileged" or doc.resource_type == "legal_advice":
            if actor.org == O.BANK: return deny("BANK_PRIVILEGE")
        if any(item.classification == "privileged" or item.resource_type == "legal_advice" for item in sources[1:]) and actor.org == O.BANK:
            return deny("BANK_PRIVILEGE")  # no generic sanitization flag can release privileged advice
        if any(item.classification == "clean_team" for item in sources):
            if not (doc.sanitized and doc.antitrust_approved and doc.classification == "ordinary"):
                return deny("ANTITRUST_RELEASE_REQUIRED")
        if not doc.approved_snapshot_hash or doc.approved_snapshot_hash != snapshot(db,doc): return deny("PACKAGE_CHANGED")
    from kestrel.services.finding_release_guard import denial as retained_package_denial
    reason=retained_package_denial(db,doc,sources)
    if reason:return deny(reason)
    return {"allowed":True,"reason_code":"PERMITTED","policy_version":"document-abac-1"}


def require(db, actor, doc, action, now):
    """Enforce the same decision used by checker and authorization endpoints."""
    result = evaluate(db, actor, doc, action, now)
    if not result['allowed']:
        raise HTTPException(403, 'Document access denied: '+result['reason_code'])
    return result


def require_retained(db,actor,current,classification,scope,action,now):
    """AND current authority with immutable workflow-record restrictions.

    The detached projection is evaluated by the same PDP; it never changes the
    source policy or grants a weaker classification to a retained record.
    """
    from types import SimpleNamespace
    from kestrel.services.documents import FIELDS
    require(db,actor,current,action,now)
    retained=SimpleNamespace(**{f:getattr(current,f) for f in FIELDS})
    retained.classification=classification;retained.clean_team_scope=scope
    return require(db,actor,retained,action,now)
