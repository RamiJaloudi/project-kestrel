import json
from typing import Literal
from fastapi import APIRouter,Depends
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from kestrel.api.auth import identity,database
from kestrel.models import GovernanceVersion
from kestrel.models import Matter
from kestrel.domain import Organization
from kestrel.services import governance as service

router=APIRouter(prefix='/api/v1/policy-editor',tags=['Policy editor and legal playbooks'])

@router.get('/matters')
def permitted_matters(actor=Depends(identity),db=Depends(database)):
    if actor[2].org!=Organization.FIRM:return []
    return [{'id':m.id,'name':m.name} for m in db.scalars(select(Matter).where(Matter.id.in_(actor[2].matters-actor[2].walls)))]


class Draft(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    matter_id:str
    kind:Literal['legal_playbook','environment_policy','wall_policy']
    name:str=Field(min_length=1,max_length=128)
    base_playbook_id:str | None=Field(default=None,max_length=36)
    definition:dict


class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    expected_revision:int=Field(ge=1)
    rationale:str=Field(min_length=5,max_length=1000)

class Edit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:int=Field(ge=1)
    definition:dict


def output(row):
    return {'id':row.id,'matter_id':row.matter_id,'kind':row.kind,'name':row.name,'author_id':row.author_id,
            'definition':json.loads(row.definition_json),'content_hash':row.content_hash,'state':row.state,
            'base_playbook_id':row.base_playbook_id,'revision':row.revision,'reviewer_id':row.reviewer_id,'review_rationale':row.review_rationale}


@router.get('')
def versions(matter_id:str,actor=Depends(identity),db=Depends(database)):
    service.access(actor[2],matter_id)
    rows=db.scalars(select(GovernanceVersion).where(GovernanceVersion.matter_id==matter_id))
    return [output(service.read(db,actor[2],r.id)) for r in rows]


@router.post('',status_code=201)
def create(payload:Draft,actor=Depends(identity),db=Depends(database)):
    return output(service.create(db,actor[2],payload))


@router.get('/{version_id}')
def get(version_id:str,actor=Depends(identity),db=Depends(database)):
    return output(service.read(db,actor[2],version_id))

@router.patch('/{version_id}')
def edit(version_id:str,payload:Edit,actor=Depends(identity),db=Depends(database)):
    row=service.read(db,actor[2],version_id)
    return output(service.edit(db,actor[2],row,payload.definition,payload.expected_revision))


@router.post('/{version_id}/test')
def test(version_id:str,actor=Depends(identity),db=Depends(database)):
    row=service.read(db,actor[2],version_id)
    return service.test_playbook(db,actor[2],row)


@router.post('/{version_id}/{operation}')
def transition(version_id:str,operation:Literal['submit','approve','reject','publish'],payload:Decision,
               actor=Depends(identity),db=Depends(database)):
    row=service.read(db,actor[2],version_id)
    return output(service.transition(db,actor[2],row,operation,payload.expected_revision,payload.rationale))
