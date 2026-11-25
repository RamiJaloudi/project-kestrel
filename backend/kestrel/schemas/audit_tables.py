"""Typed metadata-only audit queries; the selector remains the authority."""
from typing import Annotated,Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator


class Strict(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)


Category=Literal['administrative','legal_sme','clean_team','access']
Column=Literal['id','occurred_at','actor_id','category','matter_id','object_id','clean_team_scope','action','outcome','correlation_id']
Format=Literal['jsonl','csv','html','pdf']


class AuditFilters(Strict):
    category:Category
    matter_id:str|None=Field(default=None,min_length=1,max_length=128)
    from_time:int|None=Field(default=None,ge=0,le=9223372036854775807,strict=True)
    to_time:int|None=Field(default=None,ge=0,le=9223372036854775807,strict=True)

    @model_validator(mode='after')
    def ordered_window(self):
        if self.from_time is not None and self.to_time is not None and self.from_time>self.to_time:raise ValueError('From time must precede to time')
        return self


class AuditTableQuery(Strict):
    draw:int=Field(default=0,ge=0,le=2147483647,strict=True)
    start:int=Field(default=0,ge=0,le=1000000,strict=True)
    length:int=Field(default=20,ge=1,le=50,strict=True)
    sort:Column='occurred_at'
    direction:Literal['asc','desc']='desc'
    search:str=Field(default='',max_length=128)
    column_filters:dict[Column,Annotated[str,Field(max_length=128)]]=Field(default_factory=dict,max_length=10)
    audit_filters:AuditFilters


class AuditTableExport(AuditTableQuery):
    format:Format='jsonl'


class AuditMetadata(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str
    occurred_at:int
    actor_id:str|None
    category:Category
    matter_id:str|None
    object_id:str|None
    clean_team_scope:str|None
    action:str
    outcome:str
    correlation_id:str|None


class AuditTablePage(BaseModel):
    model_config=ConfigDict(extra='forbid')
    draw:int=Field(ge=0,strict=True)
    recordsTotal:int=Field(ge=0,le=1000,strict=True)
    recordsFiltered:int=Field(ge=0,le=1000,strict=True)
    data:list[AuditMetadata]=Field(max_length=50)
    count_basis:str
