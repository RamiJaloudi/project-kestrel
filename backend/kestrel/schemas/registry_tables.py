"""Scoped administrative registry grids, without legal-source capabilities."""
from typing import Annotated,Literal
from pydantic import BaseModel,ConfigDict,Field


class Strict(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)


AccessColumn=Literal['id','account_id','matter_id','username','organization','assigned','blocked','effective_blocked','active']
HistoryColumn=Literal['id','matter_id','kind','rationale','actor_id','target_id','occurred_at','revision']


class Common(Strict):
    matter_id:str=Field(min_length=1,max_length=128)
    draw:int=Field(default=0,ge=0,le=2147483647,strict=True)
    start:int=Field(default=0,ge=0,le=1000000,strict=True)
    length:int=Field(default=20,ge=1,le=50,strict=True)
    direction:Literal['asc','desc']='asc'
    search:str=Field(default='',max_length=128)


class RegistryAccessQuery(Common):
    sort:AccessColumn='username'
    column_filters:dict[AccessColumn,Annotated[str,Field(max_length=128)]]=Field(default_factory=dict,max_length=9)


class RegistryHistoryQuery(Common):
    sort:HistoryColumn='revision'
    direction:Literal['asc','desc']='desc'
    column_filters:dict[HistoryColumn,Annotated[str,Field(max_length=128)]]=Field(default_factory=dict,max_length=8)


class Output(BaseModel):model_config=ConfigDict(extra='forbid')


class RegistryAccessRow(Output):
    id:str
    account_id:str
    matter_id:str
    username:str
    organization:str
    assigned:bool
    blocked:bool
    effective_blocked:bool
    active:bool


class RegistryHistoryRow(Output):
    id:str
    matter_id:str
    kind:str
    rationale:str
    actor_id:str
    target_id:str|None
    occurred_at:int
    revision:int


class Page(Output):
    draw:int=Field(ge=0,strict=True)
    recordsTotal:int=Field(ge=0,strict=True)
    recordsFiltered:int=Field(ge=0,strict=True)
    matter_revision:int=Field(ge=1,strict=True)
    count_basis:str


class RegistryAccessPage(Page):data:list[RegistryAccessRow]=Field(max_length=50)
class RegistryHistoryPage(Page):data:list[RegistryHistoryRow]=Field(max_length=50)


class RegistryContext(Output):
    matter_id:str
    matter_name:str
    client_id:str
    client_name:str
    client_number:str
    matter_number:str
    client_matter_number:str
    validation_status:str
    revision:int


class RegistryTarget(Output):
    account_id:str
    username:str
    organization:str
    assigned:bool
    blocked:bool
    effective_blocked:bool
    active:bool
    matter_revision:int
