"""Resolve legacy UUID pairs or exact numeric-string registry pairs."""
from sqlalchemy import select
from kestrel.models import Client,MatterValidation

def resolve(db,client_id,matter_id):
    if client_id.isascii() and client_id.isdigit() and matter_id.isascii() and matter_id.isdigit():
        return db.scalar(select(MatterValidation).join(Client,Client.id==MatterValidation.client_id).where(Client.client_number==client_id,MatterValidation.matter_number==matter_id))
    row=db.get(MatterValidation,matter_id)
    return row if row and row.client_id==client_id else None

def next_number(db,column,predicate=None):
    statement=select(column)
    if predicate is not None:statement=statement.where(predicate)
    used=set(db.scalars(statement))
    value=900000
    while str(value) in used:value+=1
    return str(value)
