"""Deterministic document ABAC. Attributes are server sourced, never model decisions."""
import hashlib
import json
from sqlalchemy import select, text
from kestrel.models import DocumentPolicyVersion as Doc, PolicySource

TYPES = {"sanitized_document", "contract", "licence", "pricing", "financial", "legal_advice", "client_upload", "finding", "tracker", "report", "export"}
ACTIONS = {"read", "download", "analyze", "edit", "export", "export_metadata", "share", "historical_read", "triage"}
FIELDS = ["id", "matter_id", "document_id", "source_hash", "resource_type", "classification", "classification_confirmed",
          "review_state", "released", "audience", "quarantined", "superseded", "signing_frozen", "ai_restricted",
          "clean_team_scope", "sanitized", "antitrust_approved"]


def load(db, version_id):
    return db.scalar(select(Doc).from_statement(text("SELECT * FROM vw_document_policy_state WHERE id=:id")), {"id":version_id})


def lineage(db, doc, seen=None):
    seen = set() if seen is None else set(seen)
    if doc.id in seen:
        raise ValueError("Cyclic lineage")
    seen.add(doc.id)
    result = [doc]
    for source_id in db.scalars(select(PolicySource.source_id).where(PolicySource.artifact_id == doc.id)):
        source = load(db, source_id)
        if source is None:
            raise ValueError("Missing source")
        result.extend(lineage(db, source, seen))
    return result


def snapshot(db, doc):
    from kestrel.models import PolicyRecipient
    rows = [{key:getattr(item,key) for key in FIELDS} for item in lineage(db,doc)]
    for row in rows:
        recipients=sorted(db.scalars(select(PolicyRecipient.account_id).where(PolicyRecipient.policy_id==row['id'])))
        if recipients:row['named_recipients']=recipients
        from kestrel.services.content_labels import policy_records
        attributes=policy_records(db,row['id'])
        if attributes:row['content_attributes']=attributes
    return hashlib.sha256(json.dumps(sorted(rows,key=lambda r:r['id']),sort_keys=True).encode()).hexdigest()


def evaluate(db, actor, doc, action, now):
    """Compatibility entry point; all decisions delegate to canonical policy."""
    from kestrel.services.policy import evaluate as decide
    return decide(db, actor, doc, action, now)
