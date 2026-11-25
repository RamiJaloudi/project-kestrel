from typing import Literal
from pydantic import Field,model_validator
from kestrel.schemas.review_work import Input,Reason

class CalendarCreate(Input):
    matter_id:str=Field(min_length=1,max_length=36)
    name:str=Field(min_length=3,max_length=96)
    expected_previous_version:int=Field(default=0,ge=0)
    timezone:str=Field(min_length=1,max_length=96)
    weekdays:list[int]=Field(min_length=1,max_length=7)
    holidays:list[str]=Field(default_factory=list,max_length=1000)
    start_minute:int=Field(ge=0,le=1439)
    end_minute:int=Field(ge=1,le=1440)
    @model_validator(mode='after')
    def ordered(self):
        if self.end_minute<=self.start_minute or len(set(self.weekdays))!=len(self.weekdays) or any(d<0 or d>6 for d in self.weekdays):raise ValueError('Valid distinct weekdays and non-overnight hours required')
        return self

class PolicyCreate(Input):
    matter_id:str=Field(min_length=1,max_length=36)
    calendar_id:str=Field(min_length=1,max_length=36)
    name:str=Field(min_length=3,max_length=96)
    expected_previous_version:int=Field(default=0,ge=0)
    stage:Literal['review','qc','specialized_legal','financial','ai_coordination']
    max_business_seconds:int=Field(ge=60,le=31536000)
    exclude_paused:bool
    idle_timeout_seconds:int=Field(ge=60,le=900)

class PolicyDecision(Reason):
    expected_revision:int=Field(ge=0)
    content_hash:str=Field(min_length=64,max_length=64)

class SlaBind(Reason):
    policy_id:str=Field(min_length=1,max_length=36)
    expected_revision:int=Field(ge=1)
    request_key:str=Field(min_length=8,max_length=128)

class SessionBegin(Input):
    expected_revision:int=Field(ge=1)
    request_key:str=Field(min_length=8,max_length=128)

class SessionReceipt(Input):
    expected_sequence:int=Field(ge=0)
    request_key:str=Field(min_length=8,max_length=128)
    operation:Literal['sample','close']
    interaction:bool=Field(strict=True)
