"""Pinned internal finding projections with retained assessment-chain authority."""
import json
from dataclasses import dataclass
from fastapi import HTTPException
from sqlalchemy import select
from kestrel import models as m
from kestrel.adapters.extraction import canonical,digest
from kestrel.repositories.identity import principal
from kestrel.schemas.data_tables import Findings
from kestrel.services import workflow as w
from kestrel.services.auth import clock,authenticate

COLUMNS=['id','revision_id','revision','source_id','file_name','logical_key','version_number','summary','origin','rule_id',
    'topic','severity','materiality','exposure','workflow_status','review_state','classification','owner_id','owner','due_on','created_at','historical']
UNAVAILABLE={403,404,409,413}


@dataclass
class Scope:
    row:object
    policy:object
    rows:list
    policies:list
    sources:list
    integrity_hash:str


def material(row):return {c.name:getattr(row,c.name) for c in row.__table__.columns}


def chain_rows(db,key):
    revisions=list(db.scalars(select(m.LegalFindingRevision).where(m.LegalFindingRevision.record_key==key).order_by(m.LegalFindingRevision.version_number).limit(501)))
    if len(revisions)>500:raise HTTPException(413,'Finding assessment history exceeds the local review limit')
    candidate=db.get(m.SourceFinding,revisions[-1].candidate_id) if revisions and revisions[-1].candidate_id else db.get(m.SourceFinding,key)
    if not revisions and candidate is None:raise HTTPException(404,'Finding unavailable')
    previous=None
    for index,row in enumerate(revisions,1):
        if row.version_number!=index or row.previous_id!=previous or row.candidate_id!=(candidate.id if candidate else None):raise HTTPException(409,'Finding assessment chain integrity failed')
        previous=row.id
    return ([candidate] if candidate else [])+revisions


def evidence_integrity(source,row):
    try:
        units={unit['number']:unit for unit in json.loads(source.units_json)}
        items=json.loads(row.evidence_json)
        if not items:raise ValueError()
        for item in items:
            unit=units.get(item['unit']);start=item['start'];end=item['end']
            if not unit or type(start) is not int or type(end) is not int or not 0<=start<end<=len(unit['text']) or unit['text'][start:end]!=item['quote']:raise ValueError()
    except (KeyError,TypeError,ValueError):raise HTTPException(409,'Finding evidence integrity failed') from None


def authorize_chain(db,actor,key,historical=False,*,export=False):
    rows=chain_rows(db,key);current=rows[-1];source=db.get(m.SourceVersion,current.source_id)
    if source is None:raise HTTPException(409,'Finding source unavailable')
    w.legal(actor,source.matter_id);w.source(db,actor,source.id,historical)
    policies={};sources={}
    for row in rows:
        bound,source_policy=w.source(db,actor,row.source_id,True);w.source_integrity(bound,source_policy)
        if bound.matter_id!=source.matter_id:raise HTTPException(409,'Finding source scope integrity failed')
        evidence_integrity(bound,row);sources[bound.id]=bound
        policy=db.get(m.DocumentPolicyVersion,row.policy_id)
        if not policy or policy.resource_type!='finding' or policy.matter_id!=source.matter_id:raise HTTPException(409,'Finding policy integrity failed')
        w.require_policy(db,actor,policy,'export_metadata' if export else 'historical_read' if policy.superseded or historical else 'read')
        try:lineage=w.lineage(db,policy)
        except ValueError:raise HTTPException(409,'Finding policy lineage integrity failed') from None
        if source_policy.id not in {p.id for p in lineage}:raise HTTPException(409,'Finding source lineage missing')
        for item in lineage:
            policies[item.id]=item
            linked=db.scalar(select(m.SourceVersion).where(m.SourceVersion.policy_id==item.id))
            if linked:w.source_integrity(linked,item);sources[linked.id]=linked
    policy=db.get(m.DocumentPolicyVersion,current.policy_id)
    extras=[]
    candidate=rows[0] if isinstance(rows[0],m.SourceFinding) else None
    if candidate:
        review=db.scalar(select(m.FindingReview).where(m.FindingReview.finding_id==candidate.id))
        job=db.get(m.AnalysisJob,candidate.job_id)
        if review:extras.append(material(review))
        if job and job.document_version_id==candidate.source_id:extras.append(material(job))
    version=digest(canonical({'rows':[material(r) for r in rows],'policies':sorted([(p.id,w.snapshot(db,p)) for p in policies.values()]),
        'sources':sorted([(s.id,s.bytes_hash,s.text_hash) for s in sources.values()]),'extras':extras}).encode())
    return Scope(current,policy,rows,list(policies.values()),list(sources.values()),version)


def eligible_person(db,uid,key,historical=False):
    account=db.get(m.Account,uid) if uid else None
    if not account or not account.active:return None
    try:authorize_chain(db,principal(db,account,clock()),key,historical)
    except HTTPException as error:
        if error.status_code not in UNAVAILABLE:raise
        return None
    return {'id':account.id,'username':account.username}


def keys(db,matter,source_id=None):
    source_ids=select(m.SourceVersion.id).where(m.SourceVersion.matter_id==matter)
    if source_id:source_ids=source_ids.where(m.SourceVersion.id==source_id)
    candidates=list(db.scalars(select(m.SourceFinding.id).where(m.SourceFinding.source_id.in_(source_ids))))
    manual=list(db.scalars(select(m.LegalFindingRevision.record_key).where(m.LegalFindingRevision.source_id.in_(source_ids),m.LegalFindingRevision.candidate_id.is_(None)).distinct()))
    return sorted(set(candidates+manual))


def project(db,actor,scope,historical=False):
    from kestrel.services import diligence as d
    value=d.output(db,scope.row,scope.policy)
    result={key:value.get(key) for key in COLUMNS if key!='historical'}
    result['historical']=db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,scope.row.source_id).policy_id).superseded
    return result


def collect(db,actor,matter,filters=None,ids=None,*,export=False,versions=None):
    w.legal(actor,matter);filters=filters or Findings();result=[]
    selected=keys(db,matter,filters.source_id)
    if filters.record_key:selected=[k for k in selected if k==filters.record_key]
    if ids is not None:selected=[k for k in selected if k in set(ids)]
    for key in selected:
        try:
            scope=authorize_chain(db,actor,key,filters.historical,export=export)
            if versions is not None and versions.get(key)!=scope.row.id:continue
            row=project(db,actor,scope,filters.historical)
        except HTTPException as error:
            if error.status_code not in UNAVAILABLE:raise
            continue
        if any(getattr(filters,k) is not None and row[k]!=getattr(filters,k) for k in ['review_state','topic','severity','materiality','exposure','workflow_status','origin']):continue
        if filters.register_filter in {'risks','consents'} and row['review_state']!='reviewed':continue
        if filters.register_filter=='consents' and row['topic'] not in {'change_of_control','assignment','termination'}:continue
        if filters.status=='active' and (row['review_state']=='rejected' or row['workflow_status']=='resolved'):continue
        if filters.status=='pending' and not (row['review_state']=='candidate' or row['severity']=='unassessed'):continue
        result.append((row,scope))
    return result


def signature(records):return digest(canonical([(row,scope.integrity_hash) for row,scope in records]).encode())


def event(db,actor,scope,operation):
    # Emit one immutable scoped receipt for every contributing clean-team partition.
    restricted={p.clean_team_scope:p for p in scope.policies if p.classification=='clean_team' and p.clean_team_scope}
    for policy in restricted.values() or [scope.policy]:w.event(db,actor,policy,operation,scope.row.record_key if isinstance(scope.row,m.LegalFindingRevision) else scope.row.id)


def owner_scopes(db,actor,source_id,finding_id=None,historical=False):
    source,policy=w.source(db,actor,source_id,historical);w.legal(actor,source.matter_id);w.source_integrity(source,policy)
    selected=[finding_id] if finding_id else keys(db,source.matter_id,source.id)
    scopes=[authorize_chain(db,actor,key,historical) for key in selected]
    if any(scope.row.source_id!=source.id for scope in scopes):raise HTTPException(403,'Finding owner scope unavailable')
    return source,scopes


def owners(db,actor,source_id,finding_id=None,historical=False):
    source,scopes=owner_scopes(db,actor,source_id,finding_id,historical);result=[]
    for account in db.scalars(select(m.Account).where(m.Account.active==True).order_by(m.Account.username)):
        other=principal(db,account,clock())
        try:
            w.legal(other,source.matter_id);w.source(db,other,source.id,historical)
            for scope in scopes:
                key=scope.row.record_key if isinstance(scope.row,m.LegalFindingRevision) else scope.row.id
                authorize_chain(db,other,key,historical)
        except HTTPException as error:
            if error.status_code not in UNAVAILABLE:raise
            continue
        result.append({'id':account.id,'username':account.username})
        if len(result)>500:raise HTTPException(413,'Eligible finding owner directory exceeds local limit')
    return result


def writable(db,source,*,assessment=False):
    policy=db.get(m.DocumentPolicyVersion,source.policy_id)
    frozen=db.scalar(select(m.MatterLifecycle.frozen).where(m.MatterLifecycle.matter_id==source.matter_id))
    return bool(not policy.superseded and not policy.signing_frozen and not frozen and (not assessment or policy.classification_confirmed))


def new_owners(db,actor,source_id,historical=False):
    source,_=w.source(db,actor,source_id,historical);w.legal(actor,source.matter_id);result=[]
    for account in db.scalars(select(m.Account).where(m.Account.active==True).order_by(m.Account.username)):
        other=principal(db,account,clock())
        try:w.legal(other,source.matter_id);w.source(db,other,source.id,historical)
        except HTTPException as error:
            if error.status_code not in UNAVAILABLE:raise
            continue
        result.append({'id':account.id,'username':account.username})
        if len(result)>500:raise HTTPException(413,'Eligible new finding owner directory exceeds local limit')
    return result


def sanitized_metadata(db,actor,source,historical=False):
    full_scope=True
    try:owner_scopes(db,actor,source.id,historical=historical)
    except HTTPException as error:
        if error.status_code!=403:raise
        full_scope=False
    review=db.scalar(select(m.DocumentReviewVersion).where(m.DocumentReviewVersion.source_id==source.id).order_by(m.DocumentReviewVersion.version_number.desc()).limit(1))
    has_jobs=db.scalar(select(m.AnalysisJob.id).where(m.AnalysisJob.document_version_id==source.id).limit(1)) is not None
    withheld_review=review is not None or not full_scope;withheld_analysis=has_jobs or not full_scope
    return {'document_review':{'title':source.file_name,'counterparty':'','scope':'other','coverage_state':'unavailable' if withheld_review else 'not_started',
            'revision':review.version_number if review and full_scope else 0 if full_scope else None,'metadata_withheld':withheld_review},
        'analysis':{'state':'unavailable' if withheld_analysis else 'not_started','engine':None,'has_completed_run':None if withheld_analysis else False,
            'coverage':[],'metadata_withheld':withheld_analysis},'source_review_available':full_scope,
        'can_edit':full_scope and writable(db,source,assessment=True)}


def profile(db,actor,source_id,matter,historical=False):
    source,policy=w.source(db,actor,source_id,historical);w.legal(actor,matter);w.source_integrity(source,policy)
    if source.matter_id!=matter:raise HTTPException(403,'Source unavailable in this matter')
    manual={'can_create_finding':writable(db,source,assessment=True),'eligible_new_owners':new_owners(db,actor,source.id,historical)}
    unavailable={'source':None,'source_review_available':False,'source_review_notice':'Complete source-review metadata is unavailable under the current retained handling evidence.','eligible_owners':[],'can_edit':False,**manual}
    try:people=owners(db,actor,source.id,historical=historical)
    except HTTPException as error:
        if error.status_code!=403:raise
        # This optional profile must not disclose other same-source finding chains,
        # nor prevent access to an independently permitted selected finding.
        return unavailable
    rows=collect(db,actor,matter,Findings(source_id=source.id,historical=historical))
    value=w.output_source(db,source,policy)
    # Legacy review/jobs have no captured historical policy receipt. Preserve
    # only the current revision concurrency input, never their user/AI text.
    value.update(sanitized_metadata(db,actor,source,historical))
    value['finding_progress']={'total':len(rows),'pending':sum(row['review_state']=='candidate' for row,_ in rows),
        'reviewed':sum(row['review_state']=='reviewed' for row,_ in rows),'rejected':sum(row['review_state']=='rejected' for row,_ in rows)}
    result={'source':value,'source_review_available':True,'eligible_owners':people,'can_edit':value['can_edit'],**manual}
    if value['document_review']['metadata_withheld'] or value['analysis']['metadata_withheld']:result['source_review_notice']='Prior analysis or review metadata is withheld because its historical handling cannot be established. These defaults are for a new review; saving retains the earlier records and does not certify their content.'
    return result


def guarded_read(db,actor,matter,request,prepare):
    from kestrel.services import data_tables as tables
    before,actor=tables.begin(db,request,matter);value=prepare(actor,True)
    actor=tables.finish(db,request,matter,before);current=prepare(actor,False)
    if canonical(value)!=canonical(current):raise HTTPException(409,'Finding content, retained scope or eligible people changed; refresh before retrying')
    db.commit();return value


def detail(db,actor,key,matter,revision_id,historical,request):
    from kestrel.services import diligence as d,data_tables as tables
    tables.throttle(actor);w.legal(actor,matter)
    def prepare(fresh,audited):
        scope=authorize_chain(db,fresh,key,historical)
        if scope.policy.matter_id!=matter:raise HTTPException(403,'Finding unavailable in this matter')
        if scope.row.id!=revision_id:raise HTTPException(409,'Finding revision changed; refresh the selected finding')
        value=d.output(db,scope.row,scope.policy);value['ai_contexts']=[];value['original_summary']=None
        output=profile(db,fresh,scope.row.source_id,matter,historical)
        output['eligible_owners']=owners(db,fresh,scope.row.source_id,key,historical);output['finding']=value
        output['can_edit']=writable(db,db.get(m.SourceVersion,scope.row.source_id),assessment=True)
        if audited:event(db,fresh,scope,'table.findings.detail')
        return output
    return guarded_read(db,actor,matter,request,prepare)


def profile_read(db,actor,source_id,matter,historical,request):
    from kestrel.services import data_tables as tables
    tables.throttle(actor);w.legal(actor,matter)
    def prepare(fresh,audited):
        value=profile(db,fresh,source_id,matter,historical)
        if audited:
            source,policy=w.source(db,fresh,source_id,historical)
            w.event(db,fresh,policy,'table.findings.source_profile',source.id)
            if value['source'] is not None or value['eligible_owners']:
                for key in keys(db,matter,source.id):event(db,fresh,authorize_chain(db,fresh,key,historical),'table.findings.source_profile_contribution')
        return value
    return guarded_read(db,actor,matter,request,prepare)


def save(db,actor,payload,request,key=None):
    from kestrel.services import diligence as d
    db.expire_all();fresh=authenticate(db,request)[2]
    result=d.save_assessment(db,fresh,payload,key,commit=False)
    db.expire_all();fresh=authenticate(db,request)[2]
    scope=authorize_chain(db,fresh,result['id'])
    if scope.row.id!=result['revision_id']:raise HTTPException(409,'Finding changed before save receipt')
    if payload.owner_id and eligible_person(db,payload.owner_id,result['id']) is None:raise HTTPException(422,'Owner must clear the complete retained finding scope')
    result=d.output(db,scope.row,scope.policy);db.commit();return result


def save_source_review(db,actor,source_id,payload,request):
    from kestrel.services import diligence as d
    db.expire_all();fresh=authenticate(db,request)[2]
    owner_scopes(db,fresh,source_id)
    result=d.save_document_review(db,fresh,source_id,payload,commit=False)
    db.expire_all();fresh=authenticate(db,request)[2]
    source,_=owner_scopes(db,fresh,source_id)
    if not writable(db,source):raise HTTPException(409,'Current unfrozen source required before review receipt')
    current=d.latest_review(db,source_id)
    if current is None or current.version_number!=result['revision']:raise HTTPException(409,'Source review changed before save receipt')
    db.commit();return result


def review_candidate(db,actor,key,payload,request):
    db.expire_all();fresh=authenticate(db,request)[2]
    row,policy=w.review_finding(db,fresh,key,payload,commit=False)
    expected_id=row.id
    db.expire_all();fresh=authenticate(db,request)[2]
    scope=authorize_chain(db,fresh,key)
    if scope.row.id!=expected_id or scope.policy.review_state!=payload.decision:raise HTTPException(409,'Finding decision changed before review receipt')
    if not writable(db,db.get(m.SourceVersion,scope.row.source_id),assessment=True):raise HTTPException(409,'Current confirmed unfrozen source required before review receipt')
    result=w.finding_output(db,scope.row,scope.policy);db.commit();return result
