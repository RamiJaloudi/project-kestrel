from fastapi import APIRouter, Depends, Request, Response, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from kestrel.services import auth
from urllib.parse import quote,unquote

router = APIRouter(prefix="/api/v1")


def database(request: Request):
    with request.app.state.sessions() as db:
        yield db


def identity(request: Request, db=Depends(database)):
    return auth.authenticate(db, request)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256, repr=False, json_schema_extra={"format":"password", "writeOnly":True})
    remember_me:bool=Field(default=False,strict=True,description='Remember username and stay signed in on this portal for 30 days')


class SessionResponse(BaseModel):
    csrf_token: str
    expires_in: int = 1800


class IdentityResponse(BaseModel):
    id: str
    organization: str
    roles: list[str]
    username:str


class RestoredSession(SessionResponse):
    identity:IdentityResponse


def identity_output(actor):
    account,session,principal=actor
    return IdentityResponse(id=account.id,organization=principal.org.value,roles=sorted(r.value for r in principal.roles),username=account.username)


def preference_origin(request):
    if request.url.scheme!='https' or request.headers.get('sec-fetch-site')=='cross-site':
        raise HTTPException(403,'Preference origin denied')
    if request.headers.get('origin') is not None:auth.same_origin(request)


@router.get('/auth/preferences')
def preferences(request:Request):
    preference_origin(request)
    raw=request.cookies.get(auth.USERNAME_COOKIE,'')
    value=unquote(raw) if len(raw)<=512 else ''
    if len(value)>128 or any(ord(c)<32 or ord(c)==127 for c in value):value=''
    return {'username':value,'remember_me':bool(value)}


@router.delete('/auth/preferences',status_code=204)
def forget_username(request:Request,response:Response):
    auth.same_origin(request)
    response.delete_cookie(auth.USERNAME_COOKIE,path='/',secure=True,httponly=True,samesite='strict')


@router.post('/auth/session',response_model=RestoredSession)
def restore_session(request:Request,db=Depends(database)):
    actor,csrf=auth.restore(db,request)
    return RestoredSession(csrf_token=csrf,expires_in=max(0,actor[1].expires_at-auth.clock()),identity=identity_output(actor))


@router.post("/auth/login", response_model=SessionResponse)
def login(payload: LoginRequest, request: Request, response: Response, db=Depends(database)):
    token, csrf = auth.login(db, request, payload.username, payload.password,payload.remember_me)
    duration=auth.REMEMBER_SECONDS if payload.remember_me else auth.SESSION_SECONDS
    response.set_cookie(auth.COOKIE, token, secure=True, httponly=True, samesite="strict", path="/",max_age=duration if payload.remember_me else None)
    if payload.remember_me:
        response.set_cookie(auth.USERNAME_COOKIE,quote(payload.username.strip().casefold(),safe=''),secure=True,httponly=True,samesite='strict',path='/',max_age=duration)
    else:
        response.delete_cookie(auth.USERNAME_COOKIE,path='/',secure=True,httponly=True,samesite='strict')
    return SessionResponse(csrf_token=csrf,expires_in=duration)


@router.get("/auth/me", response_model=IdentityResponse)
def me(actor=Depends(identity)):
    return identity_output(actor)


@router.post("/auth/logout", status_code=204)
def logout(response: Response, actor=Depends(identity), db=Depends(database)):
    account, session, principal = actor
    session.revoked = True
    auth.audit(db, "logout", "allowed", account.id)
    db.commit()
    response.delete_cookie(auth.COOKIE, path="/", secure=True, httponly=True, samesite="strict")


@router.get("/portal/navigation")
def navigation(actor=Depends(identity)):
    return {"organization": actor[2].org.value, "items": ["account"], "business_workflows": "not implemented"}


@router.get("/admin/playbooks")
@router.get("/governance/inbox")
@router.post("/governance/reanalysis/{request_id}/approve")
def future_workflow(actor=Depends(identity)):
    raise HTTPException(403, "Workflow not implemented; access denied")
