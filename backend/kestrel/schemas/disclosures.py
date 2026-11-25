from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
class Strict(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class Span(Strict):
    unit:int=Field(ge=1,strict=True)
    start:int=Field(ge=0,strict=True)
    end:int=Field(ge=1,strict=True)
class Plan(Strict):
    source_id:str=Field(min_length=1,max_length=36)
    audience:Literal['halden','castlegate']
    title:str=Field(min_length=3,max_length=160)
    purpose:str=Field(min_length=10,max_length=500)
    expires_in_days:int=Field(ge=1,le=30,strict=True)
    request_key:str=Field(min_length=8,max_length=128)
    spans:list[Span]=Field(min_length=1,max_length=100)
    rationale:str=Field(min_length=10,max_length=1000)
class Review(Strict):
    operation:Literal['approve','reject']
    content_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    rationale:str=Field(min_length=10,max_length=1000)
class Decision(Strict):
    operation:Literal['legal_approve','antitrust_approve','revoke']
    bundle_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    rationale:str=Field(min_length=10,max_length=1000)
