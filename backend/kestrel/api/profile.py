"""Self profile and administrator-managed identity metadata, never permissions."""
import hmac
import json
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response,Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from argon2.exceptions import VerificationError, InvalidHashError
from kestrel.api.auth import database, identity
from kestrel.services import auth
from kestrel.models import Account, Organization, Role, RoleGrant, ServerSession, LoginThrottle, CleanTeamMembership, MatterValidation, Client
from kestrel.schemas.account_directory import AccountMetadata,AccountDirectoryQuery,AccountDirectoryPage
from kestrel.services import account_directory as directory

router=APIRouter(prefix='/api/v1',tags=['auth'])


class Scope(BaseModel):
    matter: str
    scope: str


class Profile(BaseModel):
    id: str
    upn: str
    display_name: str
    employee_id: str
    organization: str
    roles: list[str]
    clean_team_scopes: list[Scope]
    expires_at: int
    session_stamp: str
    authorization_stamp: str


def output(db,actor):
    account,session,p=actor
    scopes=[]
    for membership,validation,client in db.execute(select(CleanTeamMembership,MatterValidation,Client).join(MatterValidation,MatterValidation.matter_id==CleanTeamMembership.matter_id).join(Client,Client.id==MatterValidation.client_id).where(CleanTeamMembership.account_id==account.id,CleanTeamMembership.revoked.is_(False),CleanTeamMembership.starts_at<=auth.clock(),CleanTeamMembership.expires_at>auth.clock())):
        if membership.matter_id in p.matters and membership.matter_id not in p.walls and client.id not in p.client_walls:
            scopes.append(Scope(matter=client.client_number+'-'+validation.matter_number,scope=membership.scope))
    scopes=sorted(scopes,key=lambda s:(s.matter,s.scope))
    stamp=auth.digest(json.dumps([sorted(r.value for r in p.roles),sorted(p.matters),sorted(p.walls),sorted(p.client_walls),[s.model_dump() for s in scopes]],sort_keys=True))
    return Profile(id=account.id,upn=account.username,display_name=account.display_name or account.username.split('@')[0],employee_id=account.employee_id,organization=p.org.value,roles=sorted(r.value for r in p.roles),clean_team_scopes=scopes,expires_at=session.expires_at,session_stamp=session.id,authorization_stamp=stamp)


@router.get('/auth/profile',response_model=Profile)
def profile(actor=Depends(identity),db=Depends(database)):
    return output(db,actor)


class PasswordChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    current_password:str=Field(min_length=1,max_length=256,repr=False,json_schema_extra={'writeOnly':True,'format':'password'})
    new_password:str=Field(min_length=15,max_length=256,repr=False,json_schema_extra={'writeOnly':True,'format':'password'})
    confirm_password:str=Field(min_length=15,max_length=256,repr=False,json_schema_extra={'writeOnly':True,'format':'password'})


class PasswordResult(BaseModel):
    csrf_token:str
    profile:Profile


@router.post('/auth/password',response_model=PasswordResult)
def password(payload:PasswordChange,request:Request,response:Response,actor=Depends(identity),db=Depends(database)):
    account=db.scalar(select(Account).where(Account.id==actor[0].id).with_for_update().execution_options(populate_existing=True))
    session=db.scalar(select(ServerSession).where(ServerSession.id==actor[1].id).execution_options(populate_existing=True))
    if session.revoked or session.expires_at<=auth.clock():raise HTTPException(401,'Authentication required')
    now=auth.clock()
    key=auth.digest('password-change:'+account.id)
    throttle=db.get(LoginThrottle,key)
    if throttle is None:
        throttle=LoginThrottle(key=key,attempts=0,window_start=now);db.add(throttle)
    if now-throttle.window_start>=900:throttle.attempts,throttle.window_start=0,now
    if throttle.attempts>=5:raise HTTPException(429,'Try again in 15 minutes')
    try:valid=auth.HASHER.verify(account.password_hash,payload.current_password)
    except (VerificationError,InvalidHashError):valid=False
    if not valid:
        throttle.attempts+=1;auth.audit(db,'account.password_change','denied',account.id);db.commit()
        raise HTTPException(400,'Current password is incorrect')
    if not hmac.compare_digest(payload.new_password.encode(),payload.confirm_password.encode()):raise HTTPException(400,'New passwords do not match')
    if hmac.compare_digest(payload.new_password.encode(),payload.current_password.encode()):raise HTTPException(400,'Choose a different password')
    account.password_hash=auth.HASHER.hash(payload.new_password);account.password_customized=True
    throttle.attempts=0
    db.execute(update(ServerSession).where(ServerSession.account_id==account.id).values(revoked=True))
    token=secrets.token_urlsafe(32);csrf=auth.csrf_for_token(token)
    replacement=ServerSession(account_id=account.id,host=session.host,expires_at=session.expires_at,token_hash=auth.digest(token),csrf_hash=auth.digest(csrf))
    db.add(replacement);auth.audit(db,'account.password_change','allowed',account.id);db.commit()
    response.set_cookie(auth.COOKIE,token,secure=True,httponly=True,samesite='strict',path='/',max_age=max(1,replacement.expires_at-now) if request.cookies.get(auth.USERNAME_COOKIE) else None)
    return PasswordResult(csrf_token=csrf,profile=output(db,(account,replacement,actor[2])))


@router.post('/auth/logout-all',status_code=204)
def logout_all(response:Response,actor=Depends(identity),db=Depends(database)):
    db.scalar(select(Account).where(Account.id==actor[0].id).with_for_update())
    db.execute(update(ServerSession).where(ServerSession.account_id==actor[0].id).values(revoked=True))
    auth.audit(db,'account.logout_all','allowed',actor[0].id);db.commit()
    response.delete_cookie(auth.COOKIE,path='/',secure=True,httponly=True,samesite='strict')


def root(actor):
    if actor[2].org.value!='firm' or 'root_admin' not in {r.value for r in actor[2].roles}:raise HTTPException(403,'Administrator required')


def metadata(db,account):
    return directory.metadata(db,account)


@router.get('/admin/accounts',response_model=list[AccountMetadata],tags=['admin'])
def accounts(request:Request,actor=Depends(identity),db=Depends(database)):
    root(actor)
    return directory.listing(db,actor,request,projection=metadata)


@router.post('/admin/accounts/query',response_model=AccountDirectoryPage,tags=['admin'])
def account_query(payload:AccountDirectoryQuery,request:Request,actor=Depends(identity),db=Depends(database)):
    root(actor)
    return directory.query(db,actor,payload,request)


@router.get('/admin/accounts/{account_id}',response_model=AccountMetadata,tags=['admin'])
def account_detail(account_id:str,request:Request,revision:int=Query(ge=1,le=2147483647),actor=Depends(identity),db=Depends(database)):
    root(actor)
    return directory.detail(db,actor,account_id,revision,request)


class MetadataEdit(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    display_name:str=Field(min_length=1,max_length=128,pattern=r'^[^\x00-\x1f\x7f]+$')
    employee_id:str=Field(min_length=1,max_length=40,pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
    expected_revision:int=Field(ge=1)


@router.patch('/admin/accounts/{account_id}',response_model=AccountMetadata,tags=['admin'])
def edit(account_id:str,payload:MetadataEdit,request:Request,actor=Depends(identity),db=Depends(database)):
    root(actor)
    return directory.edit(db,actor,account_id,payload,request)
