from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator


class Input(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)


class Reason(Input):
    rationale:str=Field(min_length=5,max_length=1000)


class TaskCreate(Reason):
    stage:Literal['review','qc','specialized_legal','financial','ai_coordination']='review'
    assignee_id:str=Field(min_length=1,max_length=36)
    request_key:str=Field(min_length=8,max_length=128)
    due_at:int | None=Field(default=None,ge=0,le=4102444800)


class TaskEvent(Reason):
    operation:Literal['accept','start','pause','resume','complete','cancel','reopen','reassign','opened','deadline']
    expected_revision:int=Field(ge=1)
    request_key:str=Field(min_length=8,max_length=128)
    assignee_id:str | None=Field(default=None,min_length=1,max_length=36)
    due_at:int | None=Field(default=None,ge=0,le=4102444800)


class CustodianCreate(Input):
    custodian_id:str | None=Field(default=None,min_length=1,max_length=36)
    display_name:str | None=Field(default=None,min_length=2,max_length=160)
    custodian_type:Literal['person','shared_mailbox','department','system'] | None=None
    upn:str | None=Field(default=None,min_length=3,max_length=254)
    custody_role:Literal['origin','copy_holder','records_owner','source_system']='origin'
    provenance:str=Field(min_length=5,max_length=1000)
    effective_from:int | None=Field(default=None,ge=0,le=4102444800)
    effective_until:int | None=Field(default=None,ge=0,le=4102444800)
    request_key:str=Field(min_length=8,max_length=128)

    @model_validator(mode='after')
    def valid(self):
        if self.custodian_id:
            if self.display_name or self.custodian_type or self.upn:raise ValueError('Existing custodian must not be overwritten')
        elif not self.display_name or not self.custodian_type:raise ValueError('New custodian name and type required')
        if self.effective_from is not None and self.effective_until is not None and self.effective_until<self.effective_from:raise ValueError('Effective date order invalid')
        return self


class PartyCreate(Input):
    name:str=Field(min_length=2,max_length=160)
    party_role:str=Field(min_length=2,max_length=64)
    provenance:str=Field(min_length=5,max_length=1000)
    request_key:str=Field(min_length=8,max_length=128)
