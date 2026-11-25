"""Permission-trimmed extractive Q&A. External answers quote reviewed releases only."""
import json
import re
from fastapi import HTTPException
from sqlalchemy import select
from kestrel.models import SourceVersion,ReleasePackage,ReportVersion,QuestionAnswer
from kestrel.services import workflow as w,reports
from kestrel.services.auth import clock,audit
from kestrel.domain import member_and_not_walled
from kestrel.adapters.extraction import canonical

STOP={'which','what','where','when','who','the','a','an','of','on','can','be','is','are','to','in','and','for','our','with','have','has','that','this','does','do','it','about','please','contract','contracts','document','documents','customer','customers','tell','me','find','show','any','all','how','would','could'}
GROUPS=[{'terminate','terminated','termination','kuendigung','kündigung','kündigen','beenden'}, {'control','kontrollwechsel'}, {'assignment','assign','assigned','abtretung','übertragung'}, {'consent','zustimmung'}, {'liability','haftung','cap','caps'}, {'exclusivity','exclusive','exklusivität'}, {'compete','competition','wettbewerbsverbot'}, {'protection','privacy','datenschutz'}, {'governing','jurisdiction','law','recht'}]

def terms(text):
    words=set(re.findall(r'[^\W_]+',text.casefold(),re.UNICODE))-STOP
    for group in GROUPS:
        if words&group:words|=group
    return words

def access(actor,matter,db=None):
    if db is not None and actor.org.value!='firm':
        from kestrel.models import MatterLifecycle
        state=db.get(MatterLifecycle,matter)
        if state and state.external_closed:raise HTTPException(403,'External workspace closed')
    if not member_and_not_walled(actor,matter):raise HTTPException(403,'Matter denied')
    if actor.org.value=='firm':w.legal(actor,matter)
    elif actor.org.value not in {'halden','castlegate'}:raise HTTPException(403,'Q&A denied')

def permitted(db,actor,ref):
    if ref['kind']=='financial':
        from kestrel import models as m
        from kestrel.services import financial
        fact=db.get(m.FinancialFact,ref['object_id'])
        if not fact:raise HTTPException(403,'Financial evidence unavailable')
        _,policy,_=financial.read(db,actor,fact)
        ops={d.operation for d in financial.history(db,fact)}
        if 'verify' not in ops or ops&{'reject','revoke'}:raise HTTPException(403,'Financial evidence no longer eligible')
    elif ref['kind']=='derivative':
        from kestrel.services.disclosures import read as read_disclosure
        _,policy=read_disclosure(db,actor,ref['object_id'])
    elif ref['kind']=='source':row,policy=w.source(db,actor,ref['object_id']);w.source_integrity(row,policy)
    elif ref['kind']=='report':_,_,policy=reports.read(db,actor,ref['object_id'])
    else:_,policy=w.package(db,actor,ref['object_id'],internal=actor.org.value=='firm')
    if w.snapshot(db,policy)!=ref['snapshot']:raise HTTPException(403,'Answer source changed; ask a new question')
    return policy

def read(db,actor,row):
    access(actor,row.matter_id,db)
    if row.actor_id!=actor.id:raise HTTPException(403,'Own Q&A history only')
    value=json.loads(row.result_json)
    if value.get('mode')=='typed_financial_evidence' and actor.org.value=='castlegate':
        from kestrel.services.financial import gate_row
        gate=gate_row(db,row.matter_id)
        if not gate or not gate.enabled:raise HTTPException(403,'Bank financial dashboard disabled')
    for ref in value.pop('_scope_refs',[]):permitted(db,actor,ref)
    for ref in value['citations']:
        policy=permitted(db,actor,ref);w.event(db,actor,policy,'qa.answer_view',row.id)
    return {'id':row.id,'question':row.question,'created_at':row.created_at,**value}

def corpus(db,actor,payload):
    access(actor,payload.matter_id,db)
    query=terms(payload.question);pool=[];eligible=0;truncated=False
    def add(policy,kind,object_id,label,text,reader=None):
        nonlocal truncated
        if not text.strip():return
        if len(pool)>=400:truncated=True;return
        score=len(query&terms(text))
        pool.append((score,{'kind':kind,'object_id':object_id,'snapshot':w.snapshot(db,policy),'label':label,'text':text,'reader':reader}))
    if actor.org.value=='firm':
        for row in db.scalars(select(SourceVersion).where(SourceVersion.matter_id==payload.matter_id).order_by(SourceVersion.created_at.desc())):
            try:
                row,policy=w.source(db,actor,row.id)
                if not policy.classification_confirmed or row.extraction_status!='ready':continue
                from kestrel.services.ocr_jobs import verified
                if not verified(db,row):continue
                w.source_integrity(row,policy)
            except HTTPException as error:
                if error.status_code!=403:raise
                continue
            eligible+=1
            if eligible>200:break
            for unit in json.loads(row.units_json):
                for match in re.finditer(r'[^\n]+(?:\n|$)',unit['text']):
                    for start in range(match.start(),match.end(),1600):
                        end=min(start+1600,match.end());text=unit['text'][start:end]
                        add(policy,'source',row.id,f"{row.logical_key} v{row.version_number} · {unit['locator']}",text,{'id':row.id,'historical':False,'unit':unit['number'],'start':start,'end':end})
    else:
        for row in db.scalars(select(ReleasePackage).join(w.Policy,ReleasePackage.policy_id==w.Policy.id).where(w.Policy.matter_id==payload.matter_id).order_by(ReleasePackage.created_at.desc())):
            try:row,policy=w.package(db,actor,row.id)
            except HTTPException as error:
                if error.status_code!=403:raise
                continue
            eligible+=1
            if eligible>200:break
            report=db.scalar(select(ReportVersion).where(ReportVersion.release_id==row.id))
            if report:
                report,_,policy=reports.read(db,actor,report.id)
                for section in json.loads(report.body_json)['sections']:add(policy,'report',report.id,report.kind+' · '+section['heading']+' · '+section['reference'],section['text'])
            else:add(policy,'release',row.id,row.title,row.summary)
    if actor.org.value in {'halden','castlegate'}:
        from kestrel.services import disclosures
        from kestrel.models import DisclosureArtifact,DisclosurePlan
        for a in db.scalars(select(DisclosureArtifact).where(DisclosureArtifact.matter_id==payload.matter_id).order_by(DisclosureArtifact.created_at.desc())):
            try:a,policy=disclosures.read(db,actor,a.id)
            except HTTPException as error:
                if error.status_code not in {403,404}:raise
                continue
            eligible+=1
            if eligible>200:break
            for unit in json.loads(a.units_json):
                for start in range(0,len(unit['text']),1600):
                    end=min(start+1600,len(unit['text']))
                    add(policy,'derivative',a.id,'Approved transcript - '+unit['locator'],unit['text'][start:end],{'id':a.id,'kind':'disclosure','historical':False,'unit':unit['number'],'start':start,'end':end})
    return [ref for _,ref in pool],{'authorized_chunks':len(pool),'truncated':truncated,'chunk_limit':400,'source_limit':200}


def ask(db,actor,payload):
    mode=getattr(payload,'mode','automatic')
    filters=getattr(payload,'financial_filters',None)
    if mode=='financial' or (mode=='automatic' and filters is not None):
        from kestrel.services.financial import answer
        return answer(db,actor,payload)
    if filters is not None:raise HTTPException(422,'Financial filters require Automatic or Financial mode')
    if mode not in {'automatic','lexical'}:raise HTTPException(409,'This retrieval mode is not yet available under the current processing/index configuration; use Automatic or Lexical BM25')
    pool,scope=corpus(db,actor,payload);query=terms(payload.question)
    from kestrel.adapters.retrieval import bm25
    ranked=bm25(payload.question+' '+' '.join(sorted(query)),[ref['label']+' '+ref['text'] for ref in pool])
    selected=[{**pool[i],'score':round(score,8)} for i,score in ranked[:getattr(payload,'top_k',8)]]
    value={'retrieval':{'version':'kestrel-router-1','requested_mode':mode,'route':'lexical_bm25',**scope,'ranker':'BM25 k1=1.5 b=0.75; bilingual risk-term query expansion','reason':'Automatic uses BM25 unless explicit typed financial filters select SQL; semantic and hybrid are explicit governed provider requests.'},'_scope_refs':scope_refs(pool),'mode':'permission_filtered_excerpts','status':'evidence_found' if selected else 'insufficient_evidence',
        'answer':'These permitted passages may help answer your question. They are exact excerpts; a lawyer must determine their application and exceptions.' if selected else 'I could not find supporting passages in the permitted searchable material. I cannot answer from the available evidence.',
        'coverage':'BM25 ranking with bilingual risk-term expansion over up to 400 authorized chunks from up to 200 permitted current source versions (firm) or approved release packages and sanitized transcripts (external). Up to eight matching passages; no completeness or legal conclusion is claimed. No live AI call.',
        'citations':selected}
    return save(db,actor,payload,value)


def save(db,actor,payload,value):
    row=QuestionAnswer(actor_id=actor.id,matter_id=payload.matter_id,question=payload.question,result_json=canonical(value),created_at=clock());db.add(row);db.flush()
    result=read(db,actor,row)
    audit(db,'qa.ask',value['status'],actor.id,category='legal_sme',matter_id=payload.matter_id,object_id=row.id)
    db.commit();return result


def scope_refs(pool):
    """Private corpus fingerprint for reauthorizing stored counts/ranking metadata."""
    unique={(r['kind'],r['object_id'],r['snapshot']):{'kind':r['kind'],'object_id':r['object_id'],'snapshot':r['snapshot']} for r in pool}
    return [unique[k] for k in sorted(unique)]
