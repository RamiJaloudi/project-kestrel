from typing import Literal
from pydantic import BaseModel,ConfigDict,Field


class MappingCreate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    matter_id:str=Field(min_length=1,max_length=36)
    name:str=Field(min_length=3,max_length=96)
    source_system:str=Field(min_length=2,max_length=96)
    expected_previous_version:int=Field(default=0,ge=0)
    columns:dict[str,str]=Field(min_length=1,max_length=40)
    delimiter:Literal[',',';','\t']=','


class BatchCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    profile_id:str=Field(min_length=1,max_length=36)
    file_name:str=Field(min_length=1,max_length=160)
    csv_text:str=Field(min_length=1,max_length=262144)
    wave:Literal['wave1','wave2','manual']='manual'
    request_key:str=Field(min_length=8,max_length=128)
    synthetic:bool=False
