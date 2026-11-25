"""Explicit source-supported dimensions; missing information stays UNKNOWN."""
from typing import Annotated,Literal
from pydantic import Field,model_validator
from kestrel.schemas.disclosures import Strict,Span

Id=Annotated[str,Field(min_length=1,max_length=36)]
Hash=Annotated[str,Field(pattern=r'^[a-f0-9]{64}$')]
Status=Literal['UNKNOWN','KNOWN']
FieldName=Literal['instruments','precision','sign','calendar','period','restatement']

def complete(value,names):
    fields=[getattr(value,name) for name in names]
    if value.status=='UNKNOWN' and any(item is not None for item in fields):raise ValueError('UNKNOWN dimensions cannot contain assumed values')
    if value.status=='KNOWN' and any(item is None for item in fields):raise ValueError('Known dimensions require explicit source-supported values')
    return value

class Identifier(Strict):
    scheme:Literal['ISIN','LEI','TICKER','OTHER']
    value:str=Field(min_length=1,max_length=80)
    venue:str|None=Field(default=None,min_length=1,max_length=64)

class Instruments(Strict):
    status:Status='UNKNOWN'
    identifiers:list[Identifier]=Field(default_factory=list,max_length=8)
    @model_validator(mode='after')
    def valid(self):
        if (self.status=='KNOWN')!=bool(self.identifiers):raise ValueError('Known instruments require explicit identifiers; unknown instruments remain empty')
        if len({(item.scheme,item.value,item.venue) for item in self.identifiers})!=len(self.identifiers):raise ValueError('Distinct identifiers required')
        return self

class Precision(Strict):
    status:Status='UNKNOWN'
    kind:Literal['decimals','precision','exact']|None=None
    value:str|None=Field(default=None,pattern=r'^(INF|-?[0-9]{1,3})$')
    label:str|None=Field(default=None,min_length=1,max_length=128)
    @model_validator(mode='after')
    def valid(self):
        complete(self,['kind','label'])
        if self.status=='UNKNOWN' and self.value is not None:raise ValueError('Unknown precision has no numeric declaration')
        if self.status=='KNOWN' and self.kind!='exact' and self.value is None:raise ValueError('Declared decimals/precision required')
        if self.kind=='exact' and self.value not in {None,'INF'}:raise ValueError('Exact precision cannot carry a conflicting finite accuracy declaration')
        if self.kind=='precision' and self.value!='INF' and int(self.value or '0')<1:raise ValueError('Significant precision must be positive')
        return self

class Sign(Strict):
    status:Status='UNKNOWN'
    presentation:Literal['minus','parentheses','plus','unsigned']|None=None
    convention:str|None=Field(default=None,min_length=1,max_length=128)
    @model_validator(mode='after')
    def valid(self):return complete(self,['presentation','convention'])

class Calendar(Strict):
    status:Status='UNKNOWN'
    kind:Literal['calendar_year','fiscal_year','52_week','53_week','other']|None=None
    label:str|None=Field(default=None,min_length=1,max_length=128)
    @model_validator(mode='after')
    def valid(self):return complete(self,['kind','label'])

class Period(Strict):
    status:Status='UNKNOWN'
    kind:Literal['annual','quarterly','year_to_date','instant','other']|None=None
    label:str|None=Field(default=None,min_length=1,max_length=128)
    @model_validator(mode='after')
    def valid(self):return complete(self,['kind','label'])

class Restatement(Strict):
    status:Status='UNKNOWN'
    kind:Literal['original','restated','amended','superseded']|None=None
    label:str|None=Field(default=None,min_length=1,max_length=128)
    @model_validator(mode='after')
    def valid(self):return complete(self,['kind','label'])

class Confidence(Strict):
    status:Literal['UNKNOWN','ASSESSMENT']='UNKNOWN'
    value:str|None=Field(default=None,pattern=r'^(0(?:\.[0-9]{1,6})?|1(?:\.0{1,6})?)$')
    basis:Literal['reviewer_assessed']|None=None
    rationale:str|None=Field(default=None,min_length=10,max_length=1000)
    @model_validator(mode='after')
    def valid(self):
        fields=[self.value,self.basis,self.rationale]
        if self.status=='UNKNOWN' and any(item is not None for item in fields):raise ValueError('Unknown confidence cannot contain an accuracy assumption')
        if self.status=='ASSESSMENT' and any(item is None for item in fields):raise ValueError('Explicit uncalibrated assessment and rationale required')
        return self

class Dimensions(Strict):
    instruments:Instruments=Field(default_factory=Instruments)
    precision:Precision=Field(default_factory=Precision)
    sign:Sign=Field(default_factory=Sign)
    calendar:Calendar=Field(default_factory=Calendar)
    period:Period=Field(default_factory=Period)
    restatement:Restatement=Field(default_factory=Restatement)
    confidence:Confidence=Field(default_factory=Confidence)

class Evidence(Span):
    field:FieldName
    @model_validator(mode='after')
    def ordered(self):
        if self.end<=self.start or self.end-self.start>2000:raise ValueError('Select a bounded nonempty evidence span')
        return self

class Create(Strict):
    expected_context_hash:Hash|None=None
    dimensions:Dimensions=Field(default_factory=Dimensions)
    evidence:list[Evidence]=Field(default_factory=list,max_length=32)
    rationale:str=Field(min_length=10,max_length=1000)
    request_key:str=Field(min_length=8,max_length=128)
    @model_validator(mode='after')
    def distinct(self):
        if len({(e.field,e.unit,e.start,e.end) for e in self.evidence})!=len(self.evidence):raise ValueError('Distinct exact evidence spans required')
        return self

class Decision(Strict):
    operation:Literal['confirm','reject','revoke']
    content_hash:Hash
    content_reviewed:bool=Field(default=False,strict=True)
    rationale:str=Field(min_length=10,max_length=1000)

class Compare(Strict):
    matter_id:Id
    left_id:Id
    right_id:Id
    left_context_hash:Hash|None=None
    right_context_hash:Hash|None=None
    @model_validator(mode='after')
    def distinct(self):
        if self.left_id==self.right_id:raise ValueError('Select two distinct facts')
        return self

class Scan(Strict):
    request_key:str=Field(min_length=8,max_length=128)
    limit:int=Field(default=50,ge=1,le=50,strict=True)
    extractor:Literal['literal_rows_v1','xbrl_v1']
    rationale:str=Field(min_length=10,max_length=1000)
