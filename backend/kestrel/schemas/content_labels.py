from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
Label=Literal['legal','financial','mixed','commercial','corporate','operational','privileged','clean_team','competitively_sensitive','personal_data','export_controlled','ai_restricted','bank_eligible']
class Proposal(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    expected_revision:int=Field(ge=0,strict=True)
    request_key:str=Field(min_length=8,max_length=128)
    labels:list[Label]=Field(min_length=1,max_length=13)
    clean_team_scope:str | None=Field(default=None,min_length=1,max_length=128)
    unit_number:int | None=Field(default=None,ge=1,strict=True)
    start:int | None=Field(default=None,ge=0,strict=True)
    end:int | None=Field(default=None,ge=1,strict=True)
    rationale:str=Field(min_length=5,max_length=1000)
    @model_validator(mode='after')
    def consistent(self):
        if len(set(self.labels))!=len(self.labels):raise ValueError('Duplicate label')
        if bool(set(self.labels)&{'clean_team','competitively_sensitive'})!=bool(self.clean_team_scope):raise ValueError('Sensitive labels require an explicit named clean-team scope')
        if (self.unit_number is None)!=(self.start is None) or (self.start is None)!=(self.end is None):raise ValueError('Provide a complete evidence range or whole-document scope')
        if self.end is not None and self.end<=self.start:raise ValueError('Nonempty evidence range required')
        return self
class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    expected_revision:int=Field(ge=1,strict=True)
    rationale:str=Field(min_length=5,max_length=1000)
