"""Persistence queries; mutations are append-only through the checklist service."""
from sqlalchemy import select
from kestrel.models import ChecklistVersion as Version,ChecklistVersionDecision as Decision,ChecklistCoverageDecision as Coverage

def latest_version(db,matter):
    return db.scalar(select(Version).where(Version.matter_id==matter).order_by(Version.version_number.desc()).limit(1))
def versions(db,matter):
    return list(db.scalars(select(Version).where(Version.matter_id==matter).order_by(Version.version_number.desc())))
def latest_decision(db,version_id):
    return db.scalar(select(Decision).where(Decision.version_id==version_id).order_by(Decision.revision.desc()).limit(1))
def coverage(db,version_id,item_id):
    return db.scalar(select(Coverage).where(Coverage.version_id==version_id,Coverage.item_id==item_id).order_by(Coverage.revision.desc()).limit(1))
