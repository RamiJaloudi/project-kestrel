from datetime import date
from typing import Literal
from pydantic import Field,model_validator
from kestrel.schemas.disclosures import Strict,Span

class Fact(Strict):
    reference_kind:Literal['source','derivative']
    reference_id:str=Field(min_length=1,max_length=36)
    unit:int=Field(ge=1,strict=True)
    start:int=Field(ge=0,strict=True)
    end:int=Field(ge=1,strict=True)
    context_start:int=Field(ge=0,strict=True)
    context_end:int=Field(ge=1,strict=True)
    raw_number:str=Field(min_length=1,max_length=80)
    decimal_mark:Literal['.',',']
    numeric_notation:Literal['decimal','scientific']='decimal'
    entity:str=Field(min_length=1,max_length=160)
    metric:str=Field(min_length=1,max_length=128)
    period_label:str=Field(min_length=1,max_length=128)
    period_start:date
    period_end:date
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    scale:Literal['1','1000','1000000']
    scale_label:str=Field(min_length=1,max_length=64)
    accounting_basis:str=Field(min_length=1,max_length=128)
    consolidation_scope:str=Field(min_length=1,max_length=128)
    context_spans:list[Span]=Field(default_factory=list,max_length=16)
    @model_validator(mode='after')
    def ordered(self):
        if self.period_end<self.period_start:raise ValueError('Period end precedes start')
        if not self.context_start<=self.start<self.end<=self.context_end:raise ValueError('Numeric span must be inside its evidence context')
        return self

class Decision(Strict):
    operation:Literal['verify','reject','release','revoke']
    content_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    rationale:str=Field(min_length=10,max_length=1000)

class Gate(Strict):
    expected_revision:int=Field(ge=0,strict=True)
    enabled:bool=Field(strict=True)
    rationale:str=Field(min_length=10,max_length=1000)

class Filters(Strict):
    entity:str|None=Field(default=None,max_length=160)
    metric:str|None=Field(default=None,max_length=128)
    currency:str|None=Field(default=None,pattern=r'^[A-Z]{3}$')
    period_start:date|None=None
    period_end:date|None=None
    minimum:str|None=Field(default=None,pattern=r'^-?[0-9]{1,26}(\.[0-9]{1,12})?$')
    maximum:str|None=Field(default=None,pattern=r'^-?[0-9]{1,26}(\.[0-9]{1,12})?$')
    @model_validator(mode='after')
    def bounded(self):
        if (self.minimum is not None or self.maximum is not None) and not self.currency:raise ValueError('Amount filters require an explicit currency')
        from decimal import Decimal
        if self.minimum is not None and self.maximum is not None and Decimal(self.minimum)>Decimal(self.maximum):raise ValueError('Minimum exceeds maximum')
        return self

class Query(Filters):
    matter_id:str=Field(min_length=1,max_length=36)

class Compare(Strict):
    left_id:str=Field(min_length=1,max_length=36)
    right_id:str=Field(min_length=1,max_length=36)

class Resolution(Strict):
    operation:Literal['use_left','use_right','unresolved']
    content_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    rationale:str=Field(min_length=10,max_length=1000)
