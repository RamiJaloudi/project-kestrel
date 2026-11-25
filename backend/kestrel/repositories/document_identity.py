"""Identity projection only. Resource authorization stays with the canonical policy service."""
from uuid import uuid5,NAMESPACE_URL
from sqlalchemy import select
from fastapi import HTTPException
from kestrel.models import LogicalDocument,DocumentVersionLink,Matter


def attach(db,row):
    # Serialize creation per matter, including two concurrent imports of one logical key.
    db.scalar(select(Matter).where(Matter.id==row.matter_id).with_for_update())
    doc=db.scalar(select(LogicalDocument).where(LogicalDocument.matter_id==row.matter_id,LogicalDocument.logical_key==row.logical_key))
    if doc is None:
        doc=LogicalDocument(id=str(uuid5(NAMESPACE_URL,'kestrel:document:'+row.matter_id+':'+row.logical_key)),matter_id=row.matter_id,logical_key=row.logical_key,created_at=row.created_at)
        db.add(doc);db.flush()
    link=db.get(DocumentVersionLink,row.id)
    if link is None:
        link=DocumentVersionLink(source_id=row.id,document_id=doc.id,matter_id=row.matter_id,bytes_hash=row.bytes_hash)
        db.add(link);db.flush()
    elif (link.document_id,link.matter_id,link.bytes_hash)!=(doc.id,row.matter_id,row.bytes_hash):
        raise HTTPException(409,'Document identity projection mismatch')
    return doc
