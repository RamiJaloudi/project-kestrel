"""Read-only deterministic review signals over canonical-policy-authorized rows."""
import itertools
import json
from collections import defaultdict
from datetime import date,datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select
from kestrel import models as m
from kestrel.domain import Organization as O
from kestrel.schemas.data_tables import Sources
from kestrel.services import data_tables as tables,workflow as w,questions as q,review_work as rw,review_clocks as clocks,diligence as diligence,financial as finance
from kestrel.services.auth import clock
from kestrel.adapters import retrieval,embeddings
from kestrel.adapters.extraction import canonical,digest

VERSION='deterministic-review-intelligence-v1'
MAX_SOURCES=1000
DIMENSIONS={'workstream':['workstream','custodian','document_type'],'review':['stage','reviewer','state'],'legal':['topic','severity'],
    'financial':['entity','period','metric'],'topic':['topic','language'],'semantic':['similarity'],'hybrid':['retriever','similarity']}
TOPICS=[('Most favored nation',['most-favored-nation','most-favoured-nation','most favored nation','most favoured nation','meistbegünstigung']),
    ('Assignment and consent',['assignment','assign','abtretung','übertragung','consent','zustimmung']),('Change of control',['change of control','kontrollwechsel']),
    ('Termination',['termination','terminate','kündigung']),('Exclusivity',['exclusivity','exclusive','exklusivität']),
    ('Competition clauses',['non-compete','noncompete','wettbewerbsverbot']),('Data protection',['data protection','privacy','datenschutz']),
    ('Financial metrics',['revenue','ebitda','umsatz','cash flow'])]


def component(key,value,weight,basis,evidence=None):
    return {'key':key,'value':round(max(0,min(100,value)),4) if value is not None else None,'weight':weight,'basis':basis,'evidence':evidence or []}


def weighted_score(components):
    known=[c for c in components if c['value'] is not None];weight=sum(c['weight'] for c in known)
    score=round(sum(c['value']*c['weight'] for c in known)/weight,2) if weight else None
    status='UNKNOWN' if not weight else 'KNOWN' if len(known)==len(components) else 'PARTIAL'
    explanation='No eligible evidence for this score.' if score is None else 'Weighted mean of observed components only; unknown inputs are excluded, not treated as zero.'
    return {'status':status,'score':score,'coverage_weight':weight,'total_weight':sum(c['weight'] for c in components),'components':components,'explanation':explanation}


def unknown(domain):
    return weighted_score([component(domain,None,100,'No reviewed '+domain+' assessment or threshold is available')])


def delay_score(tasks,as_of):
    open_tasks=[t for t in tasks if t['state'] not in {'completed','cancelled'}]
    refs=[{'kind':'review_task','id':t['id'],'reader':t['_reader']} for t in open_tasks]
    known_sla=[t['timing']['sla'] for t in open_tasks if t['timing']['sla']['status'] in {'within_budget','breached'}]
    ages=[t['timing']['queue_age_seconds'] for t in open_tasks if t['timing']['queue_age_seconds'] is not None]
    reassign=[sum(e['operation']=='reassign' for e in t['_events']) for t in open_tasks]
    paused_qc=[t for t in open_tasks if t['stage']=='qc' and t['state']=='paused']
    deadlines=[min(100,max(0,(t['timing']['as_of'] or as_of)-t['due_at'])/86400*100) for t in open_tasks if t['due_at'] is not None]
    return weighted_score([
        component('sla_overdue',max((min(100,s['overdue_business_seconds']/s['budget_seconds']*100) for s in known_sla),default=None),40,'Pinned published business-calendar SLA overdue / budget, capped at 100',refs),
        component('queue_age',max((min(100,max(0,a-5*86400)/(5*86400)*100) for a in ages),default=None),20,'Demo fallback: elapsed queue age above five calendar days / five calendar days; not a business-calendar SLA',refs),
        component('reassignments',max((min(100,n/3*100) for n in reassign),default=None),10,'Observed reassignment count / 3, capped at 100; no inference about work quality',refs),
        component('paused_qc',100 if paused_qc else 0 if open_tasks else None,10,'Explicitly paused QC task; pause is not a legal finding',refs),
        component('manual_deadline',max(deadlines,default=None),10,'Explicit task deadline overdue / one elapsed day, capped at 100; separate from business-calendar SLA',refs),
        component('stalled_active_sessions',None,10,'UNKNOWN: unobserved or quiet reading does not establish a stalled review'),
    ])


def legal_score(findings):
    reviewed=[f for f in findings if f['review_state']=='reviewed']
    severities={'critical':100,'high':75,'medium':50,'low':25,'information':0}
    severity=[severities[f['severity']] for f in reviewed if f['severity'] in severities]
    material=[100 if f['materiality']=='material' else 0 for f in reviewed if f['materiality'] in {'material','not_material'}]
    refs=[{'kind':'finding','id':f['revision_id'],'reader':{'id':f['source_id'],'historical':False,**{k:f['evidence'][0][k] for k in ['unit','start','end']}}} for f in reviewed if f['evidence']]
    return weighted_score([component('reviewed_severity',max(severity,default=None),70,'Highest lawyer-reviewed severity: critical 100, high 75, medium 50, low 25, information 0',refs),
        component('reviewed_materiality',max(material,default=None),20,'Lawyer-reviewed material=100, not_material=0; undetermined remains unknown',refs),
        component('transaction_deadline',None,10,'UNKNOWN: no reviewed transaction-deadline urgency assessment is bound to this record')])


def financial_score(rows,peers):
    eligible=[r for r in rows if r['state'] in {'verified','released'}]
    compared=[]
    dimensions=['entity','metric','period_start','period_end','currency','accounting_basis','consolidation_scope']
    for row in eligible:
        for other in peers:
            if row['id']==other['id'] or other['state'] not in {'verified','released'}:continue
            if all(row[k]==other[k] for k in dimensions):compared.append((row,other))
    different=any(a['amount_text']!=b['amount_text'] for a,b in compared)
    refs=[{'kind':'financial_fact','id':r['id'],'reader':r['reader']} for r in eligible]
    return weighted_score([
        component('comparable_variance',100 if different else 0 if compared else None,60,'Different exact amounts among authorized verified facts with identical entity, metric, dates, currency, basis and scope; does not choose an authoritative value',refs),
        component('financial_materiality',None,20,'UNKNOWN: no approved monetary materiality threshold or exposure assessment is configured'),
        component('period_consistency',None,10,'UNKNOWN: different valid periods are not assumed inconsistent without a reviewed comparison policy'),
        component('verified_evidence',0 if eligible else None,10,'Eligible facts have exact evidence verified under the existing financial workflow',refs),
    ])


def financial_records(db,actor,p):
    q.access(actor,p.matter_id,db)
    if actor.org==O.BANK:
        finance.require_bank_gate(db,p.matter_id)
    filters=p.financial_filters
    stmt=select(m.FinancialFact).where(m.FinancialFact.matter_id==p.matter_id).order_by(m.FinancialFact.created_at,m.FinancialFact.id)
    if filters:
        for key in ['entity','metric','currency','period_start','period_end']:
            value=getattr(filters,key)
            if value is not None:stmt=stmt.where(getattr(m.FinancialFact,key)==str(value))
    rows=[]
    for fact in db.scalars(stmt):
        try:
            finance.read(db,actor,fact)
            if filters:
                from decimal import Decimal
                if filters.minimum is not None and fact.amount<Decimal(filters.minimum):continue
                if filters.maximum is not None and fact.amount>Decimal(filters.maximum):continue
            if len(rows)>=MAX_SOURCES:raise HTTPException(413,'Narrow the financial filters; this baseline supports at most 1000 permitted matching facts')
            value=finance.output(db,actor,fact,view_action='intelligence.financial.scope')
            # Parent source IDs remain private even for sanitized financial facts.
            rows.append((fact.source_id,value))
        except HTTPException as e:
            if e.status_code!=403:raise
    return rows


def source_records(db,actor,p):
    w.legal(actor,p.matter_id)
    sources=tables.inventory(db,actor,p.matter_id,p.source_filters or Sources())
    if len(sources)>MAX_SOURCES:raise HTTPException(413,'Narrow the source filters; this baseline supports at most 1000 permitted matching documents')
    findings=diligence.visible_findings(db,actor,p.matter_id,audited=False)
    facts=financial_records(db,actor,p);by_source=defaultdict(list)
    for sid,fact in facts:by_source[sid].append(fact)
    peers=[f for _,f in facts];rows=[];text_bytes=0
    alert_task_ids=set(db.scalars(select(m.IntelligenceAlert.task_id).where(m.IntelligenceAlert.matter_id==p.matter_id)))
    for meta,policy in sources:
        src,policy=w.source(db,actor,meta['id'],historical=bool(p.source_filters and p.source_filters.historical))
        tasks=[]
        for task in db.scalars(select(m.ReviewTask).where(m.ReviewTask.source_id==src.id).order_by(m.ReviewTask.id)):
            if task.id in alert_task_ids:continue  # Follow-up alerts cannot recursively score themselves.
            try:
                task,history=rw.task_row(db,actor,task.id);last=history[-1]
                tasks.append({'id':task.id,'stage':task.stage,'state':last.to_state,'due_at':last.due_at,'assignee':rw.person(db,last.assignee_id),'timing':clocks.metrics(db,actor,task,history),'_events':[{'id':e.id,'operation':e.operation} for e in history],'_reader':{'id':src.id,'historical':policy.superseded,'taskId':task.id}})
            except HTTPException as e:
                if e.status_code!=403:raise
        custodians=[]
        for link in db.scalars(select(m.DocumentCustodian).where(m.DocumentCustodian.source_id==src.id)):
            try:
                value=rw.custodian_output(db,actor,link)
                if not value['retired'] and (link.effective_from is None or link.effective_from<=clock()) and (link.effective_until is None or link.effective_until>clock()):custodians.append(value['custodian']['display_name'])
            except HTTPException as e:
                if e.status_code!=403:raise
        profile=diligence.latest_review(db,src.id);own=[f for f in findings if f['source_id']==src.id]
        text='';units=[]
        if p.view in {'topic','semantic','hybrid'} or p.search:
            from kestrel.services.ocr_jobs import verified
            if policy.classification_confirmed and src.extraction_status=='ready' and verified(db,src):
                w.source_integrity(src,policy);units=json.loads(src.units_json)
                text='\n'.join(u['text'] for u in units)[:16000]
                text_bytes+=len(text.encode())
                if text_bytes>2*1024*1024:raise HTTPException(413,'Narrow source filters; lexical dashboard corpus is bounded to 2 MiB')
        topics=[label for label,triggers in TOPICS if any(term in text.casefold() for term in triggers)]
        row={'id':src.id,'title':profile.title if profile else src.file_name,'language':src.language,'document_type':policy.resource_type,
            'reader':{'id':src.id,'historical':policy.superseded},'scores':{'delay':delay_score(tasks,clock()),'legal':legal_score(own),'financial':financial_score(by_source[src.id],peers)},
            'tasks':tasks,'_policy':policy,'_source':src,'_text':text,'_units':units,'_paths':{}}
        row['_paths']['workstream']=[list(parts) for parts in itertools.product(sorted({t['stage'] for t in tasks}) or ['UNKNOWN'],sorted(set(custodians)) or ['UNKNOWN'],[policy.resource_type])]
        row['_paths']['review']=[[t['stage'],t['assignee']['name'],t['state']] for t in tasks] or [['UNKNOWN','UNKNOWN','UNKNOWN']]
        row['_paths']['legal']=[[f['topic'],f['severity']] for f in own if f['review_state']=='reviewed'] or [['UNKNOWN','UNKNOWN']]
        row['_paths']['topic']=[[label,src.language] for label in topics] or [['UNKNOWN',src.language]]
        row['_signal_revision']=digest(canonical({'task_events':sorted(e['id'] for t in tasks for e in t['_events']),'findings':sorted(f['revision_id'] for f in own),'facts':sorted(f['content_hash'] for f in by_source[src.id])}).encode())
        rows.append(row)
    return rows


def cached_vectors(db,actor,row):
    src,policy=row['_source'],row['_policy'];result=[]
    try:w.require_policy(db,actor,policy,'analyze');w.processing_allowed(db,policy,external=True)
    except HTTPException as e:
        if e.status_code not in {403,409}:raise
        return result
    for vector in db.scalars(select(m.SourceEmbedding).where(m.SourceEmbedding.source_id==src.id,m.SourceEmbedding.source_snapshot==w.snapshot(db,policy),m.SourceEmbedding.model_version==embeddings.VERSION).order_by(m.SourceEmbedding.id).limit(9)):
        try:
            rw.retained(db,actor,vector)
            unit=next((u for u in row['_units'] if u['number']==vector.unit_number),None)
            if unit is None or not 0<=vector.start_offset<vector.end_offset<=len(unit['text']):raise HTTPException(409,'Cached embedding evidence unavailable')
            if digest(vector.vector_json.encode())!=vector.vector_hash or digest(unit['text'][vector.start_offset:vector.end_offset].encode())!=vector.text_hash:raise HTTPException(409,'Cached embedding integrity mismatch')
            result.append(embeddings.vector(json.loads(vector.vector_json)))
        except HTTPException as e:
            if e.status_code!=403:raise
        if len(result)>=8:break
    return result


def related(db,actor,p,rows):
    seed=next((row for row in rows if row['id']==p.seed_source_id),None)
    if not seed:raise HTTPException(403,'Choose a currently authorized seed document')
    vectors=cached_vectors(db,actor,seed)
    if not vectors:raise HTTPException(409,'Seed has no current authorized cached embedding; create governed embeddings separately. This dashboard makes no provider calls')
    semantic=[]
    for i,row in enumerate(rows):
        targets=cached_vectors(db,actor,row)
        score=max((retrieval.cosine(a,b) for a in vectors for b in targets),default=None)
        row['similarity']=round(score,6) if score is not None else None
        band='UNKNOWN' if score is None else 'Cosine >= 0.8' if score>=.8 else 'Cosine >= 0.5' if score>=.5 else 'Cosine < 0.5'
        row['_paths']['semantic']=[[band]];row['_paths']['hybrid']=[['Cached semantic + BM25',band]]
        if score is not None and score>0:semantic.append((i,score))
    semantic.sort(key=lambda x:(-x[1],x[0]))
    if p.view=='hybrid':
        lexical=retrieval.bm25(p.search or seed['_text'][:2000],[r['_text'] for r in rows])
        ranks=retrieval.rrf([[i for i,_ in lexical],[i for i,_ in semantic]])
    else:ranks=semantic
    lookup={i:score for i,score in ranks}
    for i,row in enumerate(rows):row['retrieval_score']=round(lookup[i],8) if i in lookup else None
    return rows


def collect(db,actor,p):
    q.access(actor,p.matter_id,db)
    if actor.org!=O.FIRM and p.view!='financial':raise HTTPException(403,'External intelligence is limited to individually released financial evidence')
    if p.view=='financial':
        facts=financial_records(db,actor,p);peers=[f for _,f in facts]
        return [{'id':f['id'],'title':f['entity']+' / '+f['metric'],'reader':{**f['reader'],'historical':False},'fact':{k:f[k] for k in ['entity','metric','period_start','period_end','currency','amount_text','state','accounting_basis','consolidation_scope']},
            'scores':{'delay':unknown('delay'),'legal':unknown('legal'),'financial':financial_score([f],peers)},'_paths':{'financial':[[f['entity'],f['period_start']+' to '+f['period_end'],f['metric']]]}} for _,f in facts]
    rows=source_records(db,actor,p)
    return related(db,actor,p,rows) if p.view in {'semantic','hybrid'} else rows


def project(rows,p):
    dimensions=DIMENSIONS[p.view]
    if len(p.path)>len(dimensions):raise HTTPException(422,'Cluster path is deeper than this view')
    authorized=len(rows)
    if p.search and p.view not in {'hybrid','semantic'}:
        ranked=retrieval.bm25(p.search,[r['title']+' '+r.get('_text','')+' '+json.dumps(r.get('fact',{}),ensure_ascii=False) for r in rows])
        scores={i:round(score,8) for i,score in ranked};rows=[{**r,'retrieval_score':scores[i]} for i,r in enumerate(rows) if i in scores]
    rows=[r for r in rows if any(path[:len(p.path)]==p.path for path in r['_paths'][p.view])]
    groups=defaultdict(set)
    if len(p.path)<len(dimensions):
        for row in rows:
            for path in row['_paths'][p.view]:
                if path[:len(p.path)]==p.path:groups[path[len(p.path)]].add(row['id'])
    grouped=sorted(groups.items(),key=lambda item:(-len(item[1]),item[0].casefold()))
    def order(row):
        score=row['scores'][p.sort]['score'] if p.sort!='title' else None
        return (row['title'].casefold(),row['id']) if p.sort=='title' else (score is None,-score if score is not None else 0,row['title'].casefold(),row['id'])
    rows.sort(key=order)
    def public(row):
        value={k:v for k,v in row.items() if not k.startswith('_')}
        if 'tasks' in value:value['tasks']=[{k:v for k,v in t.items() if not k.startswith('_')} for t in value['tasks']]
        return value
    return {'version':VERSION,'view':p.view,'dimensions':dimensions,'path':p.path,'level':dimensions[len(p.path)] if len(p.path)<len(dimensions) else 'document',
        'authorized_count':authorized,'matched_count':len(rows),'group_count':len(groups),'groups':[{'key':key,'label':key,'count':len(ids)} for key,ids in grouped[p.group_start:p.group_start+p.length]],
        'group_more':len(grouped)>p.group_start+p.length,'start':p.start,'length':p.length,'rows':[public(r) for r in rows[p.start:p.start+p.length]],
        'count_basis':'Distinct currently authorized records. Multi-membership groups can overlap; child counts must not be summed.',
        'scoring_basis':'Three independent deterministic scores. UNKNOWN inputs do not become zero. No combined priority, automatic legal conclusion, AI explanation or monetary threshold is inferred.',
        'cluster_basis':'Lexical topics are literal indicators; BM25 ranks only the current authorized bounded corpus. Semantic uses current verified cached embeddings only, up to eight chunks per source, without provider calls. Cosine bands are navigation choices, not calibrated probabilities.',
        'alerts':'Existing independently approved SLA plans supply durable deduped operational alerts. New hot-document alert policies and overrides are not created by this read-only view.'}


def query(db,actor,p,request):
    tables.throttle(actor);before,actor=tables.begin(db,request,p.matter_id)
    from kestrel.services.intelligence_governance import apply
    rows=apply(db,actor,p,collect(db,actor,p));result=project(rows,p)
    actor=tables.finish(db,request,p.matter_id,before)
    # Reauthorize every contributing row again before returning even aggregate counts.
    for row in rows:
        if p.view=='financial':finance.read(db,actor,db.get(m.FinancialFact,row['id']))
        else:w.source(db,actor,row['id'],historical=bool(p.source_filters and p.source_filters.historical))
    from kestrel.services.auth import audit
    audit(db,'intelligence.'+p.view+'.view','allowed',actor.id,category='access',matter_id=p.matter_id)
    db.commit();return {**result,'as_of':clock()}
