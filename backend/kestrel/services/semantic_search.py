"""On-demand, policy-filtered source embeddings; external derivative vectors remain disabled."""
import json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from kestrel import models as m
from kestrel.services import questions as q,workflow as w,review_work as rw,ai_budget
from kestrel.services.auth import clock,authenticate,audit
from kestrel.adapters import embeddings as e,retrieval
from kestrel.adapters.extraction import canonical,digest


def cache(db,actor,ref):
    anchor=ref['reader']
    row=db.scalar(select(m.SourceEmbedding).where(m.SourceEmbedding.source_id==ref['object_id'],m.SourceEmbedding.source_snapshot==ref['snapshot'],m.SourceEmbedding.unit_number==anchor['unit'],m.SourceEmbedding.start_offset==anchor['start'],m.SourceEmbedding.end_offset==anchor['end'],m.SourceEmbedding.model_version==e.VERSION))
    if row:
        rw.retained(db,actor,row)
        if digest(row.vector_json.encode())!=row.vector_hash or row.text_hash!=digest(ref['text'].encode()):raise HTTPException(409,'Embedding cache integrity mismatch')
        return row,e.vector(json.loads(row.vector_json))
    return None,None


def ask(db,sessions,request,actor,p):
    w.legal(actor,p.matter_id)
    if not p.request_key:raise HTTPException(422,'Explicit semantic/hybrid request key required')
    enabled,key=e.configuration()
    if not enabled or not key:raise HTTPException(409,'Configure and enable the provider before semantic retrieval; lexical search remains available')
    pool,scope=q.corpus(db,actor,p);eligible=[];bytes_used=len(p.question.encode())
    for i,ref in enumerate(pool):
        if ref['kind']!='source':continue
        try:
            policy=q.permitted(db,actor,ref);w.require_policy(db,actor,policy,'analyze');w.processing_allowed(db,policy,external=True)
        except HTTPException as error:
            if error.status_code not in {403,409}:raise
            continue
        if len(eligible)>=32 or bytes_used+len(ref['text'].encode())>64000:break
        bytes_used+=len(ref['text'].encode());eligible.append((i,ref))
    if not eligible:raise HTTPException(409,'No readable sources are approved for cloud embeddings under the current processing policy')
    fingerprint=digest(canonical({'question':p.question,'mode':p.mode,'top_k':p.top_k,'corpus':q.scope_refs(pool),'sources':[(ref['object_id'],ref['snapshot'],ref['reader']) for _,ref in eligible],'model':e.VERSION}).encode())
    old=db.scalar(select(m.AIOperation).where(m.AIOperation.actor_id==actor.id,m.AIOperation.request_key==p.request_key))
    if old:
        if old.kind!='semantic_retrieval' or old.input_hash!=fingerprint or old.state!='succeeded':raise HTTPException(409,'Retained semantic request; changed/repeated provider requests are not sent automatically')
        return q.read(db,actor,db.get(m.QuestionAnswer,json.loads(old.result_json)['answer_id']))
    operation=m.AIOperation(actor_id=actor.id,matter_id=p.matter_id,kind='semantic_retrieval',request_key=p.request_key,input_hash=fingerprint,created_at=clock())
    db.add(operation)
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Concurrent semantic request')
    oid=operation.id
    try:
        known={};missing=[]
        for i,ref in eligible:
            row,vector=cache(db,actor,ref)
            if row:known[i]=vector
            else:missing.append((i,ref))
        texts=[p.question]+[ref['text'] for _,ref in missing]
        ai_budget.reserve(sessions,oid,operation=True)
        vectors,tokens=e.send(texts)
        if len(vectors)!=len(texts):raise HTTPException(502,'Embedding response count mismatch')
        vectors=[e.vector(v) for v in vectors]
        ai_budget.settle_embeddings(sessions,oid,tokens)
        db.expire_all();fresh=authenticate(db,request)[2];w.legal(fresh,p.matter_id)
        # Reauthorize the full lexical corpus before saving a hybrid result, not only vector candidates.
        for ref in pool:q.permitted(db,fresh,ref)
        for _,ref in eligible:
            policy=q.permitted(db,fresh,ref);w.require_policy(db,fresh,policy,'analyze');w.processing_allowed(db,policy,external=True)
        for offset,(i,ref) in enumerate(missing,1):
            existing,_=cache(db,fresh,ref)
            if not existing:
                src,policy=rw.source(db,fresh,ref['object_id'],True);a=ref['reader'];encoded=canonical(vectors[offset])
                db.add(m.SourceEmbedding(**rw.capture(src,policy),source_snapshot=ref['snapshot'],unit_number=a['unit'],start_offset=a['start'],end_offset=a['end'],text_hash=digest(ref['text'].encode()),model_version=e.VERSION,vector_json=encoded,vector_hash=digest(encoded.encode()),created_by=fresh.id,operation_id=oid,created_at=clock()))
            known[i]=vectors[offset]
        semantic=sorted([(i,retrieval.cosine(vectors[0],known[i])) for i,_ in eligible],key=lambda row:(-row[1],row[0]))
        semantic=[(i,s) for i,s in semantic if s>0]
        lexical=retrieval.bm25(p.question+' '+' '.join(sorted(q.terms(p.question))),[r['label']+' '+r['text'] for r in pool])
        ranked=semantic if p.mode=='semantic' else retrieval.rrf([[i for i,_ in lexical],[i for i,_ in semantic]])
        selected=[{**pool[i],'score':round(score,8)} for i,score in ranked[:p.top_k]]
        value={'_scope_refs':q.scope_refs(pool),'mode':'permission_filtered_excerpts','status':'evidence_found' if selected else 'insufficient_evidence','answer':'These authorized passages are ranked evidence for lawyer interpretation; ranking does not establish legal conclusions or complete diligence.' if selected else 'No supporting passages were found in the permitted bounded corpus.',
            'coverage':'On-demand semantic source retrieval covers up to 32 embedding-eligible authorized chunks; lexical hybrid can include other readable chunks. No completeness or production retrieval-quality claim.',
            'citations':selected,'retrieval':{**scope,'version':'kestrel-router-1','requested_mode':p.mode,'route':'semantic_embeddings' if p.mode=='semantic' else 'hybrid_rrf','embedding_model':e.VERSION,'embedding_chunks':len(eligible),'cache_hits':len(eligible)-len(missing),'ranker':'cosine' if p.mode=='semantic' else 'reciprocal-rank fusion k=60','reason':'Only source versions approved for this actor and cloud processing were embedded; original source authorization is never inferred from vector similarity.'}}
        answer=m.QuestionAnswer(actor_id=fresh.id,matter_id=p.matter_id,question=p.question,result_json=canonical(value),created_at=clock());db.add(answer);db.flush()
        operation=db.get(m.AIOperation,oid);operation.state='succeeded';operation.result_json=canonical({'answer_id':answer.id})
        audit(db,'qa.semantic',value['status'],fresh.id,category='legal_sme',matter_id=p.matter_id,object_id=answer.id);db.commit();return q.read(db,fresh,answer)
    except Exception as error:
        db.rollback();operation=db.get(m.AIOperation,oid)
        if operation:operation.state='failed';db.commit()
        if isinstance(error,HTTPException):raise
        raise HTTPException(503,'Semantic retrieval failed; no automatic retry. A budget reservation may require review.')
