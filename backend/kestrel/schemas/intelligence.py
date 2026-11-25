from typing import Annotated,Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from kestrel.schemas.data_tables import Sources
from kestrel.schemas.financial import Filters


class IntelligenceQuery(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    matter_id:str=Field(min_length=1,max_length=36)
    view:Literal['workstream','review','legal','financial','topic','semantic','hybrid']='workstream'
    path:list[Annotated[str,Field(min_length=1,max_length=180)]]=Field(default_factory=list,max_length=3)
    search:str=Field(default='',max_length=128)
    source_filters:Sources|None=None
    financial_filters:Filters|None=None
    seed_source_id:str|None=Field(default=None,min_length=1,max_length=36)
    profile_id:str|None=Field(default=None,min_length=1,max_length=36)
    sort:Literal['title','delay','legal','financial']='delay'
    start:int=Field(default=0,ge=0,le=100000,strict=True)
    length:int=Field(default=20,ge=1,le=50,strict=True)
    group_start:int=Field(default=0,ge=0,le=100000,strict=True)
    @model_validator(mode='after')
    def scope(self):
        if self.view=='financial' and (self.source_filters is not None or self.seed_source_id):raise ValueError('Financial view uses typed financial filters')
        if self.view!='financial' and self.financial_filters is not None:raise ValueError('Financial filters require Financial view')
        if self.view in {'semantic','hybrid'} and not self.seed_source_id:raise ValueError('Choose an authorized seed document')
        return self


class ProfileCreate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    matter_id:str=Field(min_length=1,max_length=36)
    name:str=Field(min_length=3,max_length=96)
    expected_previous_version:int=Field(ge=0,strict=True)
    weights:dict[str,dict[str,Annotated[int,Field(strict=True,ge=0,le=100)]]]=Field(default_factory=dict,max_length=3)
    alert_threshold:int=Field(default=75,ge=0,le=100,strict=True)
    minimum_coverage:int=Field(default=50,ge=1,le=100,strict=True)
    recipient_ids:list[str]=Field(min_length=1,max_length=20)
    assignee_id:str=Field(min_length=1,max_length=36)
    rationale:str=Field(min_length=10,max_length=1000)
    request_key:str=Field(min_length=8,max_length=128)
    @model_validator(mode='after')
    def people(self):
        if len(set(self.recipient_ids))!=len(self.recipient_ids) or self.assignee_id not in self.recipient_ids or any(not 1<=len(v)<=36 for v in self.recipient_ids):raise ValueError('Distinct named recipients including task assignee required')
        return self


class GovernedDecision(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    operation:Literal['approve','reject','publish','revoke']
    content_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    rationale:str=Field(min_length=10,max_length=1000)


class OverrideCreate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    source_id:str=Field(min_length=1,max_length=36)
    profile_id:str=Field(min_length=1,max_length=36)
    domain:Literal['delay','legal','financial']
    value:int=Field(ge=0,le=100,strict=True)
    base_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    expires_in_hours:int=Field(ge=1,le=168,strict=True)
    rationale:str=Field(min_length=10,max_length=1000)
    request_key:str=Field(min_length=8,max_length=128)


class AlertDisposition(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    operation:Literal['acknowledge','escalate','close']
    expected_revision:int=Field(ge=0,strict=True)
    rationale:str=Field(min_length=10,max_length=1000)
