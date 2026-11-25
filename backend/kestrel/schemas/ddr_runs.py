"""Authenticated application commands; graph state never supplies identity/approval."""
from typing import Annotated,Literal
from pydantic import Field,model_validator
from kestrel.schemas.disclosures import Strict
Id=Annotated[str,Field(min_length=1,max_length=36)]
Hash=Annotated[str,Field(pattern=r'^[a-f0-9]{64}$')]
class Create(Strict):
    matter_id:Id
    request_key:str=Field(min_length=8,max_length=128,pattern=r'^[a-zA-Z0-9_-]+$')
    finding_ids:list[Id]=Field(min_length=1,max_length=30)
    playbook_id:Id
    agent_profile_ids:list[Id]=Field(default_factory=list,max_length=14)
    title:str=Field(min_length=3,max_length=160)
    audience:Literal['halden','castlegate']
    kind:Literal['due_diligence','board_pack']='due_diligence'
    engine:Literal['offline','openai']='offline'
    rationale:str=Field(min_length=10,max_length=1000)
    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.finding_ids))!=len(self.finding_ids):raise ValueError('Distinct reviewed finding references required')
        return self
class Review(Strict):
    operation:Literal['approve','reject','revoke']
    report_hash:Hash
    draft_hash:Hash
    snapshot_hash:Hash
    config_hash:Hash
    content_reviewed:bool=Field(strict=True)
    rationale:str=Field(min_length=10,max_length=1000)
class Command(Strict):
    rationale:str=Field(min_length=10,max_length=1000)
