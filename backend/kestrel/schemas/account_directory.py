"""Administrative identity metadata only; no legal scope or credential fields."""
from typing import Annotated,Literal
from pydantic import BaseModel,ConfigDict,Field


class Strict(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)


class AccountFilters(Strict):
    organization:Literal['firm','halden','castlegate']|None=None
    active:bool|None=Field(default=None,strict=True)


Column=Literal['id','upn','display_name','employee_id','organization','roles','active','revision']


class AccountDirectoryQuery(Strict):
    draw:int=Field(default=0,ge=0,le=2147483647,strict=True)
    start:int=Field(default=0,ge=0,le=1000000,strict=True)
    length:int=Field(default=20,ge=1,le=50,strict=True)
    sort:Column='display_name'
    direction:Literal['asc','desc']='asc'
    search:str=Field(default='',max_length=128)
    column_filters:dict[Column,Annotated[str,Field(max_length=128)]]=Field(default_factory=dict,max_length=8)
    account_filters:AccountFilters=Field(default_factory=AccountFilters)


class AccountMetadata(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str
    upn:str
    display_name:str
    employee_id:str
    organization:str
    roles:list[str]
    active:bool
    revision:int


class AccountDirectoryPage(BaseModel):
    model_config=ConfigDict(extra='forbid')
    draw:int=Field(ge=0,le=2147483647,strict=True)
    recordsTotal:int=Field(ge=0,strict=True)
    recordsFiltered:int=Field(ge=0,strict=True)
    data:list[AccountMetadata]=Field(max_length=50)
    count_basis:str
