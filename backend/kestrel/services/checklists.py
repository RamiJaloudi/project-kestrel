"""Matter-scoped request coverage. A gap is not a legal finding or N/A decision."""
import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from kestrel.models import ChecklistVersion as Version,ChecklistVersionDecision as Decision,ChecklistCoverageDecision as Coverage,Account,Matter,GovernanceVersion
from kestrel.domain import Organization as O,Role as R,member_and_not_walled
from kestrel.repositories import checklists as repo
from kestrel.repositories.identity import principal,clean_scope
from kestrel.services import workflow as w,diligence,lifecycle
from kestrel.services.auth import clock,audit
from kestrel.adapters.extraction import canonical,digest
from kestrel.schemas.ddr import ChecklistItem
ROOT=Path(__file__).resolve().parents[3]
NOTICE='Coverage describes linked evidence within your permitted scope, not complete matter inventory. A gap is not a legal finding, proof of noncompliance or automatic N/A.'

def access(actor,matter):
    if actor.org!=O.FIRM or not member_and_not_walled(actor,matter) or not actor.roles&{R.ROOT_ADMIN,R.SME,R.LAWYER,R.ANTITRUST}:raise HTTPException(403,'Checklist scope denied')

def version(db,actor,key,lock=False):
    statement=select(Version).where(Version.id==key)
    if lock:statement=statement.with_for_update()
    row=db.scalar(statement)
    if row is None:raise HTTPException(404,'Checklist unavailable')
    access(actor,row.matter_id)
    if digest(row.definition_json.encode())!=row.content_hash:raise HTTPException(409,'Checklist integrity check failed')
    return row

def output(db,row):
    decision=repo.latest_decision(db,row.id)
    return {'id':row.id,'matter_id':row.matter_id,'version':row.version_number,'previous_id':row.previous_id,'author_id':row.author_id,
        'state':decision.state if decision else 'draft','revision':decision.revision if decision else 0,'content_hash':row.content_hash,
        'definition':json.loads(row.definition_json),'created_at':row.created_at}

def listing(db,actor,matter):
    access(actor,matter)
    return [output(db,version(db,actor,r.id)) for r in repo.versions(db,matter)]

def template():
    taxonomy_path=ROOT/'data/reference/CHECKLIST_TAXONOMY.json'
    taxonomy=json.loads(taxonomy_path.read_text(encoding='utf-8-sig'))
    source=json.loads((ROOT/'data/reference/CHECKLIST_SOURCE_AUDIT.json').read_text(encoding='utf-8'))
    if digest(taxonomy_path.read_bytes())!=source['taxonomy_sha256']:raise HTTPException(409,'Taxonomy changed; source audit must be refreshed')
    return {'checklist_id':'KESTREL-DDR-REQUESTS','source':{'sha256':source['sha256'],'pages':source['pages'],'source_kind':'document_request_checklist','publisher':source['publisher'],
        'source_version':'copyright-2023-footer-0523','full_text_included':False},
        'sections':[{'section_code':s['section_code'],'title':s['title'],'page_start':s['pdf_page_start'],'page_end':s['pdf_page_end'],'agent_ids':s['agent_ids']} for s in taxonomy['sections']],
        'items':[{'item_id':'KESTREL-G-CONTRACTS-001','section_code':'G','short_abstract':'Request current material customer agreements and their amendments for transaction-specific consent review.',
            'source_page':10,'required_evidence_types':['contract','licence'],'conditional_applicability':'Scope and UK, German, EU or other legal applicability must be agreed by counsel; no obligation is inferred from the source checklist.',
            'specialist_agent_id':'material_contracts','report_section_mapping':'Material contracts and transaction consents'}],
        'notice':'Original synthetic request abstraction mapped to source section G; not a reproduction of an individual source request or approved legal guidance.'}

def create(db,actor,payload):
    access(actor,payload.matter_id);lifecycle.mutable(db,payload.matter_id)
    if not actor.roles&{R.ROOT_ADMIN,R.SME}:raise HTTPException(403,'Checklist draft role required')
    db.scalar(select(Matter).where(Matter.id==payload.matter_id).with_for_update())
    definition=template()
    definition['items']=[x.model_dump(mode='json') for x in payload.items] if payload.items is not None else [ChecklistItem.model_validate(x).model_dump(mode='json') for x in definition['items']]
    if len({x['item_id'] for x in definition['items']})!=len(definition['items']):raise HTTPException(422,'Unique stable checklist item IDs required')
    sections={s['section_code']:s for s in definition['sections']}
    for item in definition['items']:
        section=sections[item['section_code']]
        if not section['page_start']<=item['source_page']<=section['page_end'] or item['specialist_agent_id'] not in section['agent_ids']:raise HTTPException(422,'Item provenance and specialist must match the audited section')
        if item['registered_tool_ids']:raise HTTPException(409,'Tool catalog approval is a later foundation batch; no tool IDs may be activated here')
        for key in item['approved_playbook_version_ids']:
            book=db.get(GovernanceVersion,key)
            if not book or book.matter_id!=payload.matter_id or book.kind!='legal_playbook' or book.state!='published':raise HTTPException(422,'Published same-matter legal playbook required')
    encoded=canonical(definition)
    if len(encoded.encode())>64000:raise HTTPException(413,'Checklist definition exceeds the supported bound')
    input_hash=digest(canonical({'matter':payload.matter_id,'base':payload.base_version_id,'definition':definition}).encode())
    key=payload.request_key or input_hash
    old=db.scalar(select(Version).where(Version.author_id==actor.id,Version.request_key==key))
    if old:
        if old.input_hash!=input_hash:raise HTTPException(409,'Request key already bound to another checklist draft')
        version(db,actor,old.id);return output(db,old)
    base=repo.latest_version(db,payload.matter_id)
    if (base.id if base else None)!=payload.base_version_id:raise HTTPException(409,'Select the current checklist version as the replacement base')
    row=Version(matter_id=payload.matter_id,version_number=(base.version_number if base else 0)+1,previous_id=base.id if base else None,
        author_id=actor.id,definition_json=encoded,content_hash=digest(encoded.encode()),request_key=key,input_hash=input_hash,created_at=clock())
    db.add(row);flush(db)
    from kestrel.migration_support.checklist_projection_v1 import project_version
    project_version(db.connection(),row.id)
    audit(db,'checklist.draft','created',actor.id,category='legal_sme',matter_id=row.matter_id,object_id=row.id)
    commit(db);return output(db,row)

def flush(db):
    try:db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'Concurrent checklist decision; refresh')

def commit(db):
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Concurrent checklist decision; refresh')

def transition(db,actor,key,operation,payload):
    row=version(db,actor,key,lock=True);lifecycle.mutable(db,row.matter_id)
    last=repo.latest_decision(db,row.id);revision=last.revision if last else 0;state=last.state if last else 'draft'
    if payload.expected_revision!=revision or payload.content_hash!=row.content_hash:raise HTTPException(409,'Checklist revision/hash changed; refresh')
    if operation=='submit':
        if actor.id!=row.author_id or state!='draft':raise HTTPException(403,'Author may submit their own draft only')
        target='submitted'
    elif operation in {'approve','reject'}:
        if R.SME not in actor.roles or actor.id==row.author_id:raise HTTPException(403,'Independent Legal SME required')
        if state!='submitted':raise HTTPException(409,'Submitted exact version required')
        target='approved' if operation=='approve' else 'rejected'
    elif operation=='publish':
        db.scalar(select(Matter).where(Matter.id==row.matter_id).with_for_update())
        if R.ROOT_ADMIN not in actor.roles and actor.id!=row.author_id:raise HTTPException(403,'Publisher role required')
        if state!='approved':raise HTTPException(409,'Exact independently approved version required')
        reviewer=db.get(Account,last.actor_id)
        if not reviewer or not reviewer.active:raise HTTPException(403,'Approver authority no longer active')
        current=principal(db,reviewer,clock());access(current,row.matter_id)
        if R.SME not in current.roles or current.id==row.author_id:raise HTTPException(403,'Independent approval no longer valid')
        for other in repo.versions(db,row.matter_id):
            if other.id!=row.id and output(db,other)['state']=='published':raise HTTPException(409,'Checklist replacement publication requires the material-change impact workflow, not implemented in this batch')
        target='published'
    else:raise HTTPException(422,'Unknown checklist operation')
    db.add(Decision(version_id=row.id,revision=revision+1,actor_id=actor.id,state=target,content_hash=row.content_hash,rationale=payload.rationale,created_at=clock()))
    audit(db,'checklist.'+operation,'allowed',actor.id,category='legal_sme',matter_id=row.matter_id,object_id=row.id);commit(db)
    return output(db,row)

def coverage_version(db,actor,key,write=False):
    row=version(db,actor,key,lock=write);w.legal(actor,row.matter_id)
    if output(db,row)['state']!='published':raise HTTPException(409,'Published checklist scope required')
    if write:lifecycle.mutable(db,row.matter_id)
    return row

def item_of(row,item_id):
    item=next((x for x in json.loads(row.definition_json)['items'] if x['item_id']==item_id),None)
    if not item:raise HTTPException(404,'Checklist item unavailable')
    return item

def linked(db,actor,row,sources,findings,owner=None,status=None):
    source_ids=set(sources);finding_ids=set(findings);snapshots={};restrictions={}
    def inherit(policy):
        for p in w.lineage(db,policy):
            value={'matter_id':p.matter_id,'classification':p.classification,'clean_team_scope':p.clean_team_scope}
            restrictions[canonical(value)]=value
    for key in finding_ids:
        finding,policy=diligence.resolve(db,actor,key)
        if policy.matter_id!=row.matter_id or policy.review_state!='reviewed':raise HTTPException(409,'Reviewed same-matter finding required')
        source_ids.add(finding.source_id)
        snapshots['finding:'+key]={'revision_id':finding.id,'policy_snapshot':w.snapshot(db,policy)}
        inherit(policy)
    for key in sorted(source_ids):
        source,policy=w.source(db,actor,key)
        if source.matter_id!=row.matter_id:raise HTTPException(403,'Evidence outside checklist scope')
        w.source_integrity(source,policy)
        if status=='VERIFIED':
            review=diligence.latest_review(db,key)
            if not policy.classification_confirmed or source.extraction_status!='ready' or not review or review.coverage_state!='complete':raise HTTPException(409,'Complete confirmed whole-document review required')
            w.require_verified_ocr(db,source)
            if any(f['review_state']=='candidate' and f['source_id']==key for f in diligence.visible_findings(db,actor,row.matter_id,audited=False)):raise HTTPException(409,'Outstanding candidate decision required')
        snapshots[key]=w.snapshot(db,policy)
        inherit(policy)
    if owner:
        account=db.get(Account,owner)
        try:
            if not account or not account.active:raise HTTPException(403,'Inactive owner')
            w.legal(principal(db,account,clock()),row.matter_id)
            for key in source_ids:diligence.owner_allowed(db,actor,key,owner)
        except HTTPException:raise HTTPException(422,'Active, assigned and source-cleared legal owner required')
    snapshots['_restrictions']=[restrictions[k] for k in sorted(restrictions)]
    return sorted(source_ids),sorted(finding_ids),snapshots

def view_coverage(db,actor,row,item,decision):
    if decision is None:return {'item_id':item['item_id'],'status':'GAP','revision':0,'source_ids':[],'finding_ids':[],'owner_id':None,'pending_na_id':None,'derived':True,'rationale':'No responsive evidence has been linked to this scoped request; this is not a finding or N/A approval.'}
    for p in json.loads(decision.source_snapshots_json).get('_restrictions',[]):
        if p['matter_id']!=row.matter_id or (p['classification']=='clean_team' and not clean_scope(db,actor.id,row.matter_id,p['clean_team_scope'] or '',clock())):raise HTTPException(403,'Retained coverage restriction denies access')
    _,_,snapshots=linked(db,actor,row,json.loads(decision.source_ids_json),json.loads(decision.finding_ids_json))
    stale=snapshots!=json.loads(decision.source_snapshots_json)
    return {'id':decision.id,'item_id':item['item_id'],'status':'NEEDS_CLARIFICATION' if stale else decision.status,'recorded_status':decision.status,
        'revision':decision.revision,'source_ids':json.loads(decision.source_ids_json),'finding_ids':json.loads(decision.finding_ids_json),'owner_id':decision.owner_id,
        'pending_na_id':decision.id if decision.kind=='na_request' else None,'pending_waiver_id':decision.id if decision.kind=='waiver_request' else None,'rationale':decision.rationale,'missing_information':decision.missing_information,
        'stale':stale,'kind':decision.kind,'actor_id':decision.actor_id,'created_at':decision.created_at,'derived':False}

def coverage(db,actor,key):
    row=coverage_version(db,actor,key);items=[]
    for item in json.loads(row.definition_json)['items']:
        try:items.append(view_coverage(db,actor,row,item,repo.coverage(db,row.id,item['item_id'])))
        except HTTPException as error:
            if error.status_code not in {403,404}:raise
    audit(db,'checklist.coverage.view','allowed',actor.id,category='legal_sme',matter_id=row.matter_id,object_id=row.id);db.commit()
    return {'version_id':row.id,'content_hash':row.content_hash,'scope_notice':NOTICE,'items':items}

def record(db,actor,row,item,prior,kind,status,rationale,source_ids,finding_ids,owner=None,missing='',request_id=None):
    source_ids,finding_ids,snapshots=linked(db,actor,row,source_ids,finding_ids,owner,status)
    if status=='PARTIAL' and not missing.strip():raise HTTPException(422,'Describe the missing information for partial coverage')
    if status in {'PARTIAL','RECEIVED','UNDER_REVIEW','VERIFIED'} and not source_ids:raise HTTPException(422,'Linked responsive evidence required')
    if any(w.source(db,actor,key)[1].resource_type not in item['required_evidence_types'] for key in source_ids):raise HTTPException(422,'Source type does not match the agreed request')
    if prior:
        retained=json.loads(prior.source_snapshots_json).get('_restrictions',[])
        values={canonical(p):p for p in snapshots['_restrictions']+retained}
        snapshots['_restrictions']=[values[k] for k in sorted(values)]
    event=Coverage(version_id=row.id,item_id=item['item_id'],revision=(prior.revision if prior else 0)+1,actor_id=actor.id,owner_id=owner,kind=kind,status=status,
        source_ids_json=canonical(source_ids),finding_ids_json=canonical(finding_ids),source_snapshots_json=canonical(snapshots),rationale=rationale,missing_information=missing,request_id=request_id,created_at=clock())
    db.add(event);flush(db)
    from kestrel.migration_support.checklist_projection_v1 import project_coverage
    project_coverage(db.connection(),event.id)
    scopes={p['clean_team_scope'] for p in snapshots['_restrictions'] if p['classification']=='clean_team'}
    # Multi-scope records are indexed in each scope; export still rechecks their full union.
    for scope in sorted(scopes) if scopes else [None]:
        audit(db,'checklist.coverage.'+kind,'allowed',actor.id,category='clean_team' if scopes else 'legal_sme',matter_id=row.matter_id,object_id=event.id,clean_team_scope=scope)
    commit(db);return view_coverage(db,actor,row,item,event)

def prior_checked(db,actor,row,item_id,expected):
    item=item_of(row,item_id);prior=repo.coverage(db,row.id,item_id)
    if expected!=(prior.revision if prior else 0):raise HTTPException(409,'Coverage revision changed; refresh')
    if prior:view_coverage(db,actor,row,item,prior)
    return item,prior

def set_coverage(db,actor,key,item_id,payload):
    row=coverage_version(db,actor,key,write=True);item,prior=prior_checked(db,actor,row,item_id,payload.expected_revision)
    # New decisions retain the union of earlier linked evidence restrictions.
    sources=set(payload.source_ids)|(set(json.loads(prior.source_ids_json)) if prior else set())
    findings=set(payload.finding_ids)|(set(json.loads(prior.finding_ids_json)) if prior else set())
    return record(db,actor,row,item,prior,'record',payload.status,payload.rationale,sorted(sources),sorted(findings),payload.owner_id,payload.missing_information)

def request_na(db,actor,key,item_id,payload):
    row=coverage_version(db,actor,key,write=True);item,prior=prior_checked(db,actor,row,item_id,payload.expected_revision)
    return record(db,actor,row,item,prior,'na_request',prior.status if prior else 'GAP',payload.rationale,json.loads(prior.source_ids_json) if prior else [],json.loads(prior.finding_ids_json) if prior else [],prior.owner_id if prior else None)

def decide_na(db,actor,key,request_id,operation,payload):
    row=coverage_version(db,actor,key,write=True)
    proposal=db.get(Coverage,request_id)
    if not proposal or proposal.version_id!=row.id or proposal.kind!='na_request':raise HTTPException(404,'Applicability request unavailable')
    if R.SME not in actor.roles or actor.id==proposal.actor_id:raise HTTPException(403,'Independent Legal SME required for N/A')
    item,prior=prior_checked(db,actor,row,proposal.item_id,payload.expected_revision)
    if prior.id!=proposal.id:raise HTTPException(409,'Applicability request superseded; review current scope')
    if view_coverage(db,actor,row,item,prior).get('stale'):raise HTTPException(409,'Evidence changed; request a fresh applicability decision')
    status='N_A_APPROVED_BY_HUMAN' if operation=='approve' else proposal.status
    return record(db,actor,row,item,prior,'na_'+operation,status,payload.rationale,json.loads(prior.source_ids_json),json.loads(prior.finding_ids_json),prior.owner_id,request_id=proposal.id)


def request_waiver(db,actor,key,item_id,payload):
    row=coverage_version(db,actor,key,write=True);item,prior=prior_checked(db,actor,row,item_id,payload.expected_revision)
    return record(db,actor,row,item,prior,'waiver_request',prior.status if prior else 'GAP',payload.rationale,json.loads(prior.source_ids_json) if prior else [],json.loads(prior.finding_ids_json) if prior else [],prior.owner_id if prior else None)


def decide_waiver(db,actor,key,request_id,operation,payload):
    row=coverage_version(db,actor,key,write=True);proposal=db.get(Coverage,request_id)
    if not proposal or proposal.version_id!=row.id or proposal.kind!='waiver_request':raise HTTPException(404,'Waiver request unavailable')
    if R.SME not in actor.roles or actor.id==proposal.actor_id:raise HTTPException(403,'Independent Legal SME required for waiver')
    item,prior=prior_checked(db,actor,row,proposal.item_id,payload.expected_revision)
    if prior.id!=proposal.id or view_coverage(db,actor,row,item,prior).get('stale'):raise HTTPException(409,'Waiver scope changed; submit a fresh request')
    return record(db,actor,row,item,prior,'waiver_'+operation,'WAIVED_BY_HUMAN' if operation=='approve' else proposal.status,payload.rationale,json.loads(prior.source_ids_json),json.loads(prior.finding_ids_json),prior.owner_id,request_id=proposal.id)
