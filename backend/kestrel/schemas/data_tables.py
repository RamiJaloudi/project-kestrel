from typing import Annotated,Literal
from uuid import UUID
from pydantic import Field,model_validator
from kestrel.schemas.disclosures import Strict
from kestrel.schemas.financial import Filters
class Sources(Strict):
    historical:bool=Field(default=False,strict=True)
    contracts_only:bool=Field(default=False,strict=True)
    classification:Literal['ordinary','privileged','clean_team']|None=None
    language:Literal['en','de','unknown']|None=None
    wave:Literal['wave1','wave2']|None=None
class Tasks(Strict):
    historical:bool=Field(default=False,strict=True)
    status:Literal['assigned','accepted','in_progress','paused','completed','cancelled']|None=None
    stage:Literal['review','qc','specialized_legal','financial','ai_coordination']|None=None
    assignee_id:str|None=Field(default=None,min_length=1,max_length=36)
    created_by:str|None=Field(default=None,min_length=1,max_length=36)
    mine:bool=Field(default=False,strict=True)
class Findings(Strict):
    historical:bool=Field(default=False,strict=True)
    register_filter:Literal['all','risks','consents']=Field(default='all',alias='register')
    status:Literal['all','active','pending']='all'
    record_key:str|None=Field(default=None,min_length=1,max_length=36)
    source_id:str|None=Field(default=None,min_length=1,max_length=36)
    review_state:Literal['candidate','reviewed','rejected']|None=None
    topic:Literal['change_of_control','assignment','exclusivity','non_compete','termination','liability_cap','governing_law','data_protection','other']|None=None
    severity:Literal['critical','high','medium','low','information','unassessed']|None=None
    materiality:Literal['material','not_material','undetermined','unassessed']|None=None
    exposure:Literal['consent','notice','termination','none','unclear']|None=None
    workflow_status:Literal['open','in_progress','resolved']|None=None
    origin:Literal['ai_candidate','lawyer']|None=None
class TableQuery(Strict):
    matter_id:str=Field(min_length=1,max_length=36)
    saved_view_id:str|None=Field(default=None,min_length=1,max_length=36)
    saved_view_version_hash:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    draw:int=Field(default=0,ge=0,le=2147483647,strict=True)
    start:int=Field(default=0,ge=0,le=1000000,strict=True)
    length:int=Field(default=20,ge=1,le=50,strict=True)
    sort:str|None=Field(default=None,min_length=1,max_length=64)
    direction:Literal['asc','desc']='asc'
    search:str=Field(default='',max_length=128)
    column_filters:dict[Annotated[str,Field(max_length=64)],Annotated[str,Field(max_length=128)]]=Field(default_factory=dict,max_length=16)
    source_filters:Sources|None=None
    financial_filters:Filters|None=None
    task_filters:Tasks|None=None
    finding_filters:Findings|None=None
    @model_validator(mode='after')
    def saved_version(self):
        if self.saved_view_version_hash is not None and self.saved_view_id is None:raise ValueError('Saved view version hash requires its saved view ID')
        return self
class TaskItem(Strict):
    id:str=Field(min_length=1,max_length=36)
    expected_revision:int=Field(ge=1,strict=True)
class TaskSelection(Strict):
    matter_id:str=Field(min_length=1,max_length=36)
    items:list[TaskItem]=Field(min_length=1,max_length=25)
    @model_validator(mode='after')
    def distinct(self):
        if len({i.id for i in self.items})!=len(self.items):raise ValueError('Select distinct tasks')
        return self
class TaskReassign(TaskSelection):
    assignee_id:str=Field(min_length=1,max_length=36)
    rationale:str=Field(min_length=5,max_length=1000)
    request_key:UUID
class Export(Strict):
    matter_id:str=Field(min_length=1,max_length=36)
    ids:list[Annotated[str,Field(min_length=1,max_length=36)]]=Field(min_length=1,max_length=100)
    format:Literal['csv','xlsx']
    historical:bool=Field(default=False,strict=True)
    finding_versions:dict[Annotated[str,Field(min_length=1,max_length=36)],Annotated[str,Field(min_length=1,max_length=36)]]|None=Field(default=None,max_length=100)
    @model_validator(mode='after')
    def unique(self):
        if len(set(self.ids))!=len(self.ids):raise ValueError('Select distinct record IDs')
        return self
