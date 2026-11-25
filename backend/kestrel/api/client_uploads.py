import json
from types import SimpleNamespace
from typing import Literal
from urllib.parse import quote
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from kestrel.api.auth import identity,database
from kestrel.models import ClientSubmission as Submission,SubmissionAcceptance as Acceptance,DocumentPolicyVersion as Policy
from kestrel.services import workflow as w
from kestrel.services.auth import clock
from kestrel.domain import Organization as O,member_and_not_walled
from kestrel.repositories.identity import clean_scope
from kestrel.adapters.extraction import extract,MAX_BYTES,canonical,digest
router=APIRouter(prefix='/api/v1/client-uploads',tags=['Halden uploads and firm intake'])

class Accept(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    logical_key:str=Field(min_length=1,max_length=96,pattern=r'^[A-Za-z0-9_-]+$')
    rationale:str=Field(min_length=10,max_length=1000)

def read(db,actor,submission_id):
    row=db.get(Submission,submission_id)
    if not row:raise HTTPException(404,'Upload unavailable')
    policy=db.get(Policy,row.policy_id);w.require_policy(db,actor,policy,'triage' if actor.org==O.FIRM else 'read')
    if row.data is None or row.parsed_json is None:raise HTTPException(410,'Client upload copy deleted; retained metadata only')
    if digest(row.data)!=row.bytes_hash or policy.source_hash!=row.bytes_hash:raise HTTPException(409,'Upload integrity failure')
    return row,policy

def output(db,row,policy,detail=False):
    accepted=db.get(Acceptance,row.id)
    value={'id':row.id,'file_name':row.file_name,'bytes_hash':row.bytes_hash,'classification':policy.classification,'uploaded_by':row.uploaded_by,'created_at':row.created_at,'accepted_source_id':accepted.source_id if accepted else None}
    if detail:value['units']=json.loads(row.parsed_json)['units']
    return value

@router.post('',status_code=201)
async def upload(request:Request,matter_id:str,file_name:str,synthetic:bool=False,handling:Literal['ordinary','privileged','clean_team']='ordinary',actor=Depends(identity),db=Depends(database)):
    user=actor[2]
    if user.org!=O.CLIENT or not member_and_not_walled(user,matter_id):raise HTTPException(403,'Assigned Halden uploader required')
    from kestrel.services.lifecycle import mutable
    mutable(db,matter_id)
    if not synthetic:raise HTTPException(422,'Confirm fictional synthetic material')
    if request.headers.get('content-type','').split(';')[0]!='application/octet-stream':raise HTTPException(415,'Binary file body required')
    content=bytearray()
    async for chunk in request.stream():
        if len(content)+len(chunk)>MAX_BYTES:raise HTTPException(413,'File exceeds 3 MiB')
        content.extend(chunk)
    parsed=await run_in_threadpool(extract,file_name,bytes(content));text='\n'.join(u['text'] for u in parsed['units']).casefold()
    if parsed.get('sensitive_hidden') and handling!='clean_team':raise HTTPException(422,'Hidden or opaque new-format content requires declared clean-team handling and current named membership')
    if handling!='clean_team' and any(word in text for word in ['privileged','internal legal advice','anwaltlich vertraulich']):handling='privileged'
    if any(word in text for word in ['clean-team','clean team','wettbewerblich sensibel']):handling='clean_team'
    if handling=='clean_team' and not clean_scope(db,user.id,matter_id,'pricing',clock()):raise HTTPException(403,'Active named pricing clean-team membership required for this upload')
    policy=Policy(matter_id=matter_id,document_id='client-submission',source_hash=parsed['bytes_hash'],resource_type='client_upload',classification=handling,classification_confirmed=False,review_state='candidate',clean_team_scope='pricing' if handling=='clean_team' else None)
    db.add(policy);db.flush();row=Submission(policy_id=policy.id,matter_id=matter_id,uploaded_by=user.id,file_name=file_name,bytes_hash=parsed['bytes_hash'],data=bytes(content),parsed_json=canonical(parsed),created_at=clock())
    db.add(row)
    try:db.flush();w.event(db,user,policy,'client_upload.submit',row.id,'awaiting_firm_intake');db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'This uploader already submitted these bytes to this matter')
    return output(db,row,policy)

@router.get('')
def listing(matter_id:str,actor=Depends(identity),db=Depends(database)):
    if not member_and_not_walled(actor[2],matter_id):raise HTTPException(403,'Matter denied')
    result=[]
    for row in db.scalars(select(Submission).where(Submission.matter_id==matter_id).order_by(Submission.created_at.desc())):
        try:row,policy=read(db,actor[2],row.id);result.append(output(db,row,policy));w.event(db,actor[2],policy,'client_upload.list',row.id)
        except HTTPException as error:
            if error.status_code not in {403,410}:raise
    db.commit();return result

@router.get('/{submission_id}')
def detail(submission_id:str,actor=Depends(identity),db=Depends(database)):
    row,policy=read(db,actor[2],submission_id);value=output(db,row,policy,True);w.event(db,actor[2],policy,'client_upload.view',row.id);db.commit();return value

@router.get('/{submission_id}/download')
def download(submission_id:str,actor=Depends(identity),db=Depends(database)):
    row,policy=read(db,actor[2],submission_id);w.event(db,actor[2],policy,'client_upload.download',row.id);db.commit()
    return Response(row.data,media_type=json.loads(row.parsed_json)['media_type'],headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row.file_name,safe='')})

@router.post('/{submission_id}/accept',status_code=201)
def accept(submission_id:str,payload:Accept,actor=Depends(identity),db=Depends(database)):
    row,policy=read(db,actor[2],submission_id);w.legal(actor[2],row.matter_id)
    if db.get(Acceptance,row.id):raise HTTPException(409,'Upload already accepted into the firm record')
    meta=SimpleNamespace(matter_id=row.matter_id,file_name=row.file_name,logical_key=payload.logical_key,classification=policy.classification,resource_type='client_upload',clean_team_scope=policy.clean_team_scope,language='unknown',governing_law='unconfirmed',wave='manual',previous_id=None)
    source,source_policy=w.intake(db,actor[2],meta,row.data,parsed=json.loads(row.parsed_json),commit=False)
    db.add(Acceptance(submission_id=row.id,source_id=source.id,actor_id=actor[2].id,rationale=payload.rationale,created_at=clock()))
    w.event(db,actor[2],policy,'client_upload.accept',row.id)
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Concurrent acceptance; refresh')
    return w.output_source(db,source,source_policy)
