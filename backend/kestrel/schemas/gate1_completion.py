from typing import Literal
from pydantic import Field,model_validator
from kestrel.schemas.review_work import Input,Reason

class RequestLog(Input):
    operation:Literal['request','follow_up','note','reference']
    expected_revision:int=Field(ge=0)
    request_key:str=Field(min_length=8,max_length=128)
    notes:str=Field(min_length=5,max_length=2000)
    due_date:str | None=Field(default=None,max_length=10)
    wave:str=Field(default='manual',min_length=1,max_length=32)
    workstream:str=Field(default='',max_length=96)
    jurisdiction:str=Field(default='Unconfirmed',max_length=160)
    source_ids:list[str]=Field(default_factory=list,max_length=50)
    import_row_id:str | None=Field(default=None,min_length=1,max_length=36)
    request_reference:str=Field(default='',max_length=160)
    disclosure_reference:str=Field(default='',max_length=160)
    @model_validator(mode='after')
    def ids(self):
        if len(set(self.source_ids))!=len(self.source_ids) or any(not 1<=len(s)<=36 for s in self.source_ids):raise ValueError('Distinct source IDs required')
        return self

class EscalationPlan(Reason):
    expected_revision:int=Field(ge=1)
    request_key:str=Field(min_length=8,max_length=128)
    warning_percent:int=Field(ge=1,le=99)
    recipient_ids:list[str]=Field(min_length=1,max_length=10)
    @model_validator(mode='after')
    def ids(self):
        if len(set(self.recipient_ids))!=len(self.recipient_ids) or any(not 1<=len(s)<=36 for s in self.recipient_ids):raise ValueError('Distinct recipient identities required')
        return self

class EscalationDecision(Reason):
    content_hash:str=Field(pattern=r'^[a-f0-9]{64}$')

class AlertDisposition(Reason):
    expected_revision:int=Field(ge=0)
    operation:Literal['acknowledge','close']
