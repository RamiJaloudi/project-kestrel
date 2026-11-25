"""Saved configurations are retained content, never authorization grants."""
from typing import Annotated,Literal
from pydantic import Field,model_validator
from kestrel.schemas.disclosures import Strict
from kestrel.schemas.data_tables import TableQuery

Id=Annotated[str,Field(min_length=1,max_length=36)]
Hash=Annotated[str,Field(pattern=r'^[a-f0-9]{64}$')]
Dataset=Literal['inventory','financial']

class EvidenceRef(Strict):
    kind:Literal['source','financial']
    id:Id

class Configuration(Strict):
    name:str=Field(min_length=1,max_length=96)
    query:TableQuery
    handling:Literal['private_unclassified','source_bound']='private_unclassified'
    evidence_refs:list[EvidenceRef]=Field(default_factory=list,max_length=50)
    rationale:str=Field(min_length=10,max_length=1000)
    request_key:str=Field(min_length=8,max_length=128)
    @model_validator(mode='after')
    def distinct(self):
        if len({(r.kind,r.id) for r in self.evidence_refs})!=len(self.evidence_refs):raise ValueError('Distinct evidence references required')
        if self.handling=='source_bound' and not self.evidence_refs:raise ValueError('Source-bound configurations require explicit evidence')
        return self

class Create(Configuration):
    matter_id:Id
    dataset:Dataset

class Version(Configuration):
    expected_version_hash:Hash

class Share(Strict):
    version_hash:Hash
    recipient_ids:list[Id]=Field(min_length=1,max_length=25)
    expires_in_days:int=Field(ge=1,le=30,strict=True)
    rationale:str=Field(min_length=10,max_length=1000)
    request_key:str=Field(min_length=8,max_length=128)
    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.recipient_ids))!=len(self.recipient_ids):raise ValueError('Distinct named recipients required')
        return self

class ShareDecision(Strict):
    operation:Literal['approve','reject','revoke']
    content_hash:Hash
    content_reviewed:bool=Field(default=False,strict=True)
    rationale:str=Field(min_length=10,max_length=1000)
