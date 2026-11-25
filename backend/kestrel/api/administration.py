from typing import Literal
from fastapi import APIRouter, Depends,Request,Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select,or_
from kestrel.api.auth import database, identity
from kestrel.models import Client, AdministrationDecision
from kestrel.services import administration as service
from kestrel.services import registry_tables
from kestrel.schemas.registry_tables import (RegistryAccessQuery,RegistryHistoryQuery,RegistryAccessPage,RegistryHistoryPage,RegistryContext,RegistryTarget)
from kestrel.services.auth import audit

router = APIRouter(prefix="/api/v1/validation", tags=["Client matter validation and ethical walls"])


def admin(actor=Depends(identity)):
    service.require_admin(actor[2])
    return actor[2]


class Named(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=128)


class ClientRequest(Named):
    client_number:str | None=Field(default=None,pattern=r'^[0-9]{1,12}$',strict=True)


class MatterRequest(Named):
    client_id: str
    matter_number:str | None=Field(default=None,pattern=r'^[0-9]{1,12}$',strict=True)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int = Field(ge=1)
    rationale: str = Field(min_length=5, max_length=1000)
    status: Literal["pending", "validated", "rejected"]


class AccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    username: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=1)
    rationale: str = Field(min_length=5, max_length=1000)
    assigned: bool
    blocked: bool
    days: int = Field(default=30, ge=1, le=365)


@router.get("/clients")
def clients(request:Request,actor=Depends(admin), db=Depends(database)):
    return registry_tables.guarded_read(db,actor,request,lambda current:service.client_rows(db,current))


@router.post("/clients", status_code=201)
def create_client(payload: ClientRequest,request:Request, actor=Depends(admin), db=Depends(database)):
    return registry_tables.write(db,actor,request,'client',payload)


@router.get("/matters")
def matters(request:Request,actor=Depends(admin), db=Depends(database)):
    return registry_tables.guarded_read(db,actor,request,lambda current:service.registry(db,current))


@router.post("/matters", status_code=201)
def create_matter(payload: MatterRequest,request:Request, actor=Depends(admin), db=Depends(database)):
    return registry_tables.write(db,actor,request,'matter',payload)


@router.post("/matters/{matter_id}/decision")
def decide(matter_id: str, payload: Decision,request:Request, actor=Depends(admin), db=Depends(database)):
    return registry_tables.write(db,actor,request,'decision',payload,matter=matter_id)


@router.get("/matters/{matter_id}/access")
def access(matter_id: str,request:Request, actor=Depends(admin), db=Depends(database)):
    return registry_tables.guarded_read(db,actor,request,lambda current:service.access_rows(db,current,matter_id),matter=matter_id)


@router.post("/matters/{matter_id}/access")
def set_access(matter_id: str, payload: AccessRequest,request:Request, actor=Depends(admin), db=Depends(database)):
    return registry_tables.write(db,actor,request,'access',payload,matter=matter_id)


@router.get("/matters/{matter_id}/history")
def history(matter_id: str,request:Request, actor=Depends(admin), db=Depends(database)):
    return registry_tables.guarded_read(db,actor,request,lambda current:[{key:row[key] for key in ['kind','rationale','actor_id','target_id','occurred_at','revision']}
        for row in registry_tables.history_rows(db,current,matter_id)],matter=matter_id)


@router.post('/tables/access/query',response_model=RegistryAccessPage)
def access_query(payload:RegistryAccessQuery,request:Request,actor=Depends(admin),db=Depends(database)):
    return registry_tables.query(db,actor,request,payload,'access')


@router.post('/tables/history/query',response_model=RegistryHistoryPage)
def history_query(payload:RegistryHistoryQuery,request:Request,actor=Depends(admin),db=Depends(database)):
    return registry_tables.query(db,actor,request,payload,'history')


@router.get('/matters/{matter_id}/context',response_model=RegistryContext)
def context(matter_id:str,request:Request,revision:int=Query(ge=1),actor=Depends(admin),db=Depends(database)):
    return registry_tables.context(db,actor,request,matter_id,revision)


@router.get('/matters/{matter_id}/access-target',response_model=RegistryTarget)
def access_target(matter_id:str,request:Request,username:str=Query(min_length=1,max_length=128),revision:int=Query(ge=1),actor=Depends(admin),db=Depends(database)):
    return registry_tables.target(db,actor,request,matter_id,username,revision)
