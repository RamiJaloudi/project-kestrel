from typing import Literal
from fastapi import APIRouter,Depends,Query,Request,HTTPException
from pydantic import Field,model_validator
from kestrel.api.auth import identity,database
from kestrel.schemas.disclosures import Strict
from kestrel.services import readers as s
router=APIRouter(prefix='/api/v1/readers',tags=['Authorized reader comparisons'])
def checked(db,actor,operation,call):
    try:return call()
    except HTTPException as error:
        if error.status_code in {401,403,409}:
            db.rollback()
            from kestrel.services.auth import audit
            audit(db,'reader.'+operation+'.denied','denied',actor.id,category='access');db.commit()
        raise
class Target(Strict):
    kind:Literal['source','derivative']
    id:str=Field(min_length=1,max_length=36)
    historical:bool=Field(default=False,strict=True)
    unit:int|None=Field(default=None,ge=1,strict=True)
    start:int|None=Field(default=None,ge=0,strict=True)
    end:int|None=Field(default=None,ge=1,strict=True)
    @model_validator(mode='after')
    def span(self):
        if (self.start is None)!=(self.end is None) or (self.start is not None and (self.unit is None or self.end<=self.start)):raise ValueError('An exact unit and ordered start/end pair are required')
        return self
class Comparison(Strict):
    matter_id:str=Field(min_length=1,max_length=36)
    targets:list[Target]=Field(min_length=2,max_length=4)
@router.get('/candidates')
def candidates(matter_id:str,request:Request,kind:Literal['source','derivative']='source',historical:bool=False,search:str=Query(default='',max_length=128),limit:int=Query(default=20,ge=1,le=50),after:str|None=Query(default=None,max_length=36),actor=Depends(identity),db=Depends(database)):
    return checked(db,actor[2],'candidates',lambda:s.candidates(db,actor[2],matter_id,kind,historical,search,limit,after,request))
@router.post('/compare')
def compare(payload:Comparison,request:Request,actor=Depends(identity),db=Depends(database)):return checked(db,actor[2],'comparison',lambda:s.compare(db,actor[2],payload,request))
