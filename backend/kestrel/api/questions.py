from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field,model_validator
from sqlalchemy import select
from kestrel.api.auth import identity,database
from kestrel.models import QuestionAnswer
from kestrel.services import questions as service
from kestrel.schemas.financial import Filters
router=APIRouter(prefix='/api/v1/questions',tags=['Permission-aware document Q&A'])

class Ask(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    matter_id:str=Field(min_length=1,max_length=36)
    question:str=Field(min_length=5,max_length=1000)
    mode:Literal['automatic','lexical','semantic','hybrid','financial']='automatic'
    top_k:int=Field(default=8,ge=1,le=8,strict=True)
    request_key:str | None=Field(default=None,min_length=8,max_length=128)
    financial_filters:Filters | None=None
    @model_validator(mode='after')
    def compatible(self):
        if self.financial_filters is not None and self.mode not in {'automatic','financial'}:raise ValueError('Financial filters require Automatic or Financial mode')
        return self

@router.post('',status_code=201)
def ask(payload:Ask,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    def prepare(fresh):
        if payload.mode in {'semantic','hybrid'}:
            from kestrel.services.semantic_search import ask as semantic_ask
            return semantic_ask(db,request.app.state.sessions,request,fresh,payload)
        return service.ask(db,fresh,payload)
    return protected(db,request,actor[2],payload.matter_id,'qa.ask',prepare)

@router.get('')
def history(matter_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    def prepare(fresh):
        service.access(fresh,matter_id,db);rows=[]
        for row in db.scalars(select(QuestionAnswer).where(QuestionAnswer.actor_id==fresh.id,QuestionAnswer.matter_id==matter_id).order_by(QuestionAnswer.created_at.desc()).limit(30)):
            try:rows.append(service.read(db,fresh,row))
            except HTTPException as error:
                if error.status_code!=403:raise
        db.commit();return rows
    return protected(db,request,actor[2],matter_id,'qa.history',prepare)

@router.get('/{answer_id}')
def answer(answer_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    row=db.get(QuestionAnswer,answer_id)
    if not row:raise HTTPException(404,'Answer unavailable')
    from kestrel.services.response_guard import protected
    return protected(db,request,actor[2],row.matter_id,'qa.read',lambda fresh:service.read(db,fresh,row))

class Synthesize(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_key:str=Field(min_length=8,max_length=128,pattern=r'^[a-zA-Z0-9_-]+$')

@router.post('/{answer_id}/synthesize',status_code=201)
def synthesize(answer_id:str,payload:Synthesize,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.qa_ai import synthesize
    value=synthesize(db,request.app.state.sessions,request,actor[2],answer_id,payload)
    db.commit();return value
