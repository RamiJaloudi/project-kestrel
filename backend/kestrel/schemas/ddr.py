from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator

Code=Literal['A','B','C','D','E','F','G','H','I','J','K','L','M','N']
Status=Literal['PARTIAL','NOT_REQUESTED','REQUESTED','RECEIVED','UNDER_REVIEW','VERIFIED','GAP','NEEDS_CLARIFICATION']
class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class ChecklistItem(Strict):
    item_id:str=Field(pattern=r'^KESTREL-[A-N]-[A-Z0-9-]{1,64}$')
    section_code:Code
    short_abstract:str=Field(min_length=10,max_length=400)
    source_page:int=Field(ge=1,le=21,strict=True)
    source_item_number:int | None=Field(default=None,ge=1,strict=True)
    authorship:Literal['original_kestrel_request_abstraction']='original_kestrel_request_abstraction'
    applicability:Literal['requires_legal_sme_review']='requires_legal_sme_review'
    required_evidence_types:list[Literal['contract','licence','pricing','financial','legal_advice','client_upload','tracker','report']]=Field(min_length=1,max_length=8)
    jurisdictions:list[str]=Field(default_factory=lambda:['UK','Germany','EU'],min_length=1,max_length=10)
    conditional_applicability:str=Field(min_length=10,max_length=600)
    specialist_agent_id:str=Field(pattern=r'^[a-z_]{1,64}$')
    report_section_mapping:str=Field(min_length=3,max_length=160)
    approved_playbook_version_ids:list[str]=Field(default_factory=list,max_length=20)
    registered_tool_ids:list[str]=Field(default_factory=list,max_length=20)
    @model_validator(mode='after')
    def stable_section(self):
        if not self.item_id.startswith('KESTREL-'+self.section_code+'-'):raise ValueError('Item ID must bind its section')
        if len(set(self.required_evidence_types))!=len(self.required_evidence_types):raise ValueError('Duplicate evidence types')
        return self
class ChecklistCreate(Strict):
    matter_id:str=Field(min_length=1,max_length=36)
    base_version_id:str | None=Field(default=None,min_length=1,max_length=36)
    request_key:str | None=Field(default=None,min_length=8,max_length=128,pattern=r'^[a-zA-Z0-9_-]+$')
    items:list[ChecklistItem] | None=Field(default=None,min_length=1,max_length=50)
class VersionDecision(Strict):
    expected_revision:int=Field(ge=0,strict=True)
    content_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    rationale:str=Field(min_length=5,max_length=1000)
class CoverageDecision(Strict):
    expected_revision:int=Field(ge=0,strict=True)
    status:Status
    source_ids:list[str]=Field(default_factory=list,max_length=50)
    finding_ids:list[str]=Field(default_factory=list,max_length=50)
    owner_id:str | None=Field(default=None,min_length=1,max_length=36)
    missing_information:str=Field(default='',max_length=1000)
    rationale:str=Field(min_length=5,max_length=1000)
    @model_validator(mode='after')
    def references(self):
        for values in [self.source_ids,self.finding_ids]:
            if len(set(values))!=len(values) or any(not 1<=len(v)<=36 for v in values):raise ValueError('Distinct bounded IDs required')
        return self
class ApplicabilityDecision(Strict):
    expected_revision:int=Field(ge=0,strict=True)
    rationale:str=Field(min_length=10,max_length=1000)
