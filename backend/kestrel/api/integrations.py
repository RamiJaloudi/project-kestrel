"""Compatibility APIs and document decisions; scoped sessions or OAuth tokens."""
import base64
import secrets
import json
import hashlib
from urllib.parse import parse_qs
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from typing import Annotated, Literal
from fastapi.security import HTTPBearer, HTTPBasic
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from argon2.exceptions import VerificationError, InvalidHashError
from kestrel.api.auth import database
from kestrel.models import (ServiceClient, ServiceToken, Account, Matter, MatterValidation,
                           Client, DocumentPolicyVersion, LoginThrottle)
from kestrel.repositories.identity import principal
from kestrel.services.auth import authenticate, HASHER, DUMMY_HASH, digest, clock, audit
from kestrel.services.documents import load, lineage
from kestrel.services.policy import evaluate
from kestrel.domain import Organization as O, Role as R, member_and_not_walled
from kestrel.models import GovernanceVersion
from kestrel.services.registry_numbers import resolve

SCOPES = {"ClientMatter.Validate","EthicalWalls.Check","Documents.Authorize"}
router = APIRouter()
bearer = HTTPBearer(auto_error=False)
basic = HTTPBasic(auto_error=False)


def caller(required_scope):
    def dependency(request: Request, token=Depends(bearer), db=Depends(database)):
        if token:
            stored = db.scalar(select(ServiceToken).where(ServiceToken.token_hash==digest(token.credentials)))
            client = db.get(ServiceClient,stored.client_id) if stored else None
            if not stored or stored.expires_at<=clock() or not client or not client.active:
                raise HTTPException(401,"Invalid service token",headers={"WWW-Authenticate":"Bearer"})
            if required_scope not in set(stored.scopes.split()) & set(client.scopes.split()):
                raise HTTPException(403,"Service scope required")
            account = db.get(Account,client.account_id)
            if not account or not account.active: raise HTTPException(401,"Inactive service identity")
            actor = principal(db,account,clock())
        else:
            actor = authenticate(db,request)[2]
        integration_roles={R.ROOT_ADMIN,R.LAWYER,R.SME,R.ANTITRUST}
        if required_scope=='EthicalWalls.Check':integration_roles.add(R.CONFLICTS)
        if required_scope != 'Documents.Authorize' and (actor.org != O.FIRM or not actor.roles & integration_roles):
            raise HTTPException(403,"Firm integration permission required")
        return actor
    return dependency


@router.post('/oauth/token',tags=['OAuth service clients'],openapi_extra={"requestBody":{"required":True,"content":{"application/x-www-form-urlencoded":{"schema":{"type":"object","required":["grant_type"],"properties":{"grant_type":{"type":"string","enum":["client_credentials"]},"scope":{"type":"string"}}}}}}})
async def token(request: Request, credentials=Depends(basic), db=Depends(database)):
    if request.url.scheme!='https': raise HTTPException(403,"HTTPS required")
    # Read bounded form body; never echo credentials or accept identity headers.
    raw = await request.body()
    if len(raw)>4096: raise HTTPException(413,"Request too large")
    if request.headers.get('content-type','').split(';')[0]!='application/x-www-form-urlencoded':
        raise HTTPException(415,"Form encoding required")
    try:
        fields=parse_qs(raw.decode(),strict_parsing=True,max_num_fields=8)
        if any(len(v)!=1 for v in fields.values()): raise ValueError()
        if credentials is None: raise ValueError()
        name,secret=credentials.username,credentials.password
    except (ValueError,UnicodeError): raise HTTPException(401,"Invalid client",headers={"WWW-Authenticate":"Basic"})
    if fields.get('grant_type')!=['client_credentials']: raise HTTPException(400,"Unsupported grant_type")
    key=digest('oauth-peer:'+request.client.host)
    throttle=db.get(LoginThrottle,key)
    if throttle is None:
        throttle=LoginThrottle(key=key,attempts=0,window_start=clock());db.add(throttle)
    if clock()-throttle.window_start>=900: throttle.attempts=0;throttle.window_start=clock()
    if throttle.attempts>=20: raise HTTPException(429,"Try later")
    throttle.attempts+=1
    client=db.scalar(select(ServiceClient).where(ServiceClient.client_name==name))
    try: valid=HASHER.verify(client.secret_hash if client else DUMMY_HASH,secret)
    except (VerificationError,InvalidHashError): valid=False
    if not valid or not client or not client.active:
        audit(db,'oauth.token','denied');db.commit();raise HTTPException(401,"Invalid client")
    scopes=set(fields.get('scope',[client.scopes])[0].split())
    if not scopes or not scopes<=set(client.scopes.split()) or not scopes<=SCOPES:
        db.commit();raise HTTPException(400,"Invalid scope")
    value=secrets.token_urlsafe(32)
    db.add(ServiceToken(client_id=client.id,token_hash=digest(value),scopes=' '.join(sorted(scopes)),expires_at=clock()+300))
    audit(db,'oauth.token','allowed',client.account_id);db.commit()
    return {"access_token":value,"token_type":"Bearer","expires_in":300,"scope":' '.join(sorted(scopes))}


class Environment(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    hosting: Literal['cloud','on-premises']
    region: Literal['US','EU','APAC','OTHER']
    aiEnabled: bool
    externalSharing: bool


class Pair(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    clientId: str=Field(min_length=1,max_length=160)
    matterId: str=Field(min_length=1,max_length=160)
    environment: Environment | None=None


def matter_result(db,actor,payload):
    validation=resolve(db,payload.clientId,payload.matterId)
    matter_id=validation.matter_id if validation else None
    valid=bool(validation and member_and_not_walled(actor,matter_id))
    # Without configured environment policies there is NO workspace authorization.
    result={"valid":valid,"reason":None if valid else "Matter unavailable or invalid for caller",
            "clientId":payload.clientId,"matterId":payload.matterId,
            "clientMatterId":payload.clientId.zfill(5)+'-'+payload.matterId.zfill(5),
            "matterStatus":"Active" if valid else "Unavailable","aiRestrictionsFlag":"Y",
            "policyRevision":validation.revision if valid else 0,"flags":[],"flagPolicies":[],
            "enforcementEnabled":True,"environmentChecked":payload.environment is not None,
            "workspaceAllowed":False,"restrictionViolations":["Environment authorization policy not configured"] if payload.environment else []}
    if valid:
        client=db.get(Client,validation.client_id)
        result.update(clientName=client.name,matterName=db.get(Matter,matter_id).name,
            clientMatterId=client.client_number+'-'+validation.matter_number)
        policies=db.scalars(select(GovernanceVersion).where(GovernanceVersion.matter_id==matter_id,
            GovernanceVersion.kind=='environment_policy',GovernanceVersion.state=='published')).all()
        if policies:
            definitions=[json.loads(p.definition_json) for p in policies]
            restrictions=[]
            result['aiRestrictionsFlag']='Y' if any(p['block_ai'] for p in definitions) else 'N'
            result['flagPolicies']=definitions
            result['policySnapshot']=hashlib.sha256(''.join(sorted(p.content_hash for p in policies)).encode()).hexdigest()
            if payload.environment:
                e=payload.environment
                for p in definitions:
                    if p['block_ai'] and e.aiEnabled:restrictions.append('AI processing prohibited')
                    if p['block_cloud'] and e.hosting=='cloud':restrictions.append('Cloud hosting prohibited')
                    if p['block_external'] and e.externalSharing:restrictions.append('External sharing prohibited')
                    if e.region not in p['allowed_regions']:restrictions.append('Region not approved')
            result['restrictionViolations']=sorted(set(restrictions))
            result['workspaceAllowed']=payload.environment is not None and not restrictions
    return result


@router.post('/api/client-matter-validations',tags=['Client–matter validation compatibility'])
def validate(payload: Pair,actor=Depends(caller('ClientMatter.Validate')),db=Depends(database)):
    result=matter_result(db,actor,payload);audit(db,'integration.matter','allowed' if result['valid'] else 'denied',actor.id);db.commit();return result


class Batch(BaseModel):
    requests: list[Pair]=Field(min_length=1,max_length=100)


@router.post('/api/client-matter-validations/batch',tags=['Client–matter validation compatibility'])
def batch(payload: Annotated[list[Pair], Body(min_length=1,max_length=100)],actor=Depends(caller('ClientMatter.Validate')),db=Depends(database)):
    result=[matter_result(db,actor,p) for p in payload]
    audit(db,'integration.batch','checked',actor.id);db.commit()
    return result


class Walls(BaseModel):
    model_config=ConfigDict(extra='forbid')
    clientId:str
    matterId:str
    emails:list[Annotated[str,Field(min_length=3,max_length=254,pattern=r'^\s*[^\s@]+@[^\s@]+\.[^\s@]+\s*$')]]=Field(max_length=100)


@router.post('/api/ethical-walls',tags=['Ethical walls compatibility'])
def walls(payload: Walls,actor=Depends(caller('EthicalWalls.Check')),db=Depends(database)):
    pair=Pair(clientId=payload.clientId,matterId=payload.matterId)
    if not matter_result(db,actor,pair)['valid']: raise HTTPException(403,"Matter access denied")
    validation=resolve(db,payload.clientId,payload.matterId)
    results=[]
    for email in dict.fromkeys(e.strip().casefold() for e in payload.emails):
        account=db.scalar(select(Account).where(Account.email==email))
        allowed=bool(account and account.active and member_and_not_walled(principal(db,account,clock()),validation.matter_id))
        results.append({"email":email,"allowed":allowed,"reason":"Assigned and unwalled" if allowed else "Unavailable, unassigned or restricted"})
    audit(db,'integration.walls','checked',actor.id);db.commit()
    return {"mode":"allow","policyRevision":validation.revision,"results":results}


class Authorization(BaseModel):
    model_config=ConfigDict(extra='forbid')
    document_version_id:str
    action:str


@router.post('/api/v1/document-authorizations',tags=['Document ABAC'])
def authorize(payload: Authorization,request:Request,actor=Depends(caller('Documents.Authorize')),db=Depends(database)):
    doc=load(db,payload.document_version_id)
    result=evaluate(db,actor,doc,payload.action,clock())
    scope=None
    if doc:
        try: scope=next((s.clean_team_scope for s in lineage(db,doc) if s.classification=='clean_team'),None)
        except ValueError: pass
    audit(db,'document.'+payload.action if payload.action in {'read','download','analyze','edit','export','export_metadata','share','historical_read','triage'} else 'document.unknown',
          'allowed' if result['allowed'] else 'denied',actor.id,category='clean_team' if scope else 'access',
          matter_id=doc.matter_id if doc else None,object_id=doc.id if doc else None,clean_team_scope=scope,
          correlation_id=getattr(request.state,'correlation_id',None));db.commit()
    return result
