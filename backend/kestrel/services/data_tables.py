"""Server-authorized table pages; client column visibility is never an access rule."""
import csv,hashlib,io,time,threading
from collections import deque
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select,bindparam
from kestrel import models as m
from kestrel.services import questions as q,workflow as w,financial as f
from kestrel.schemas.data_tables import Sources
from kestrel.schemas.financial import Query
from kestrel.domain import Organization as O
from kestrel.adapters.extraction import canonical,digest
from kestrel.services.auth import clock,authenticate
from sqlalchemy import text

SOURCE_FIELDS=['id','matter_id','logical_key','file_name','version_number','wave','extraction_status','language','created_at']
INVENTORY_COLUMNS=['id','logical_key','file_name','version_number','wave','classification','classification_confirmed','extraction_status','language','resource_type','created_at']
FINANCIAL_COLUMNS=['id','entity','metric','period_start','period_end','currency','amount_text','accounting_basis','consolidation_scope','state']
_lock=threading.Lock();_requests={}

def authorization_inputs(db,matter,actor_id):
    """Change detector over PDP inputs, not a second authorization engine or a grant."""
    now=clock();parts={};subjects={actor_id}
    source_ids=select(m.SourceVersion.id).where(m.SourceVersion.matter_id==matter)
    for model in [m.FinancialFactDecision,m.DisclosurePlanReview,m.DisclosureDecision,m.SourceAccessGrant]:
        table=model.__table__;people=[c for c in table.columns if c.name in {'account_id','actor_id'} or c.name.endswith('_by')]
        statement=select(*people)
        if 'matter_id' in table.c:statement=statement.where(table.c.matter_id==matter)
        elif 'source_id' in table.c:statement=statement.where(table.c.source_id.in_(source_ids))
        for row in db.execute(statement):subjects.update(v for v in row if v)
    client_id=db.scalar(select(m.MatterValidation.client_id).where(m.MatterValidation.matter_id==matter))
    names=['Organization','Account' ,'Role','RoleGrant','MatterAssignment','MatterValidation','EthicalWall','CleanTeamMembership','FinancialAccessGate','FinancialOrganizationGate','FinancialFactDecision','DisclosurePlan','DisclosurePlanReview','DisclosureDecision','SourceAccessGrant','ContentLabelAssertion','ContentLabelDecision','MatterLifecycle','IntelligenceProfileDecision','IntelligenceOverride','IntelligenceOverrideDecision']
    fields={'id','matter_id','client_id','account_id','organization_id','role_id','name','code','active','revoked','status','state','scope','clean_team_scope','label_scope','starts_at','expires_at','operation','content_hash','bundle_hash','snapshot_hash','revision','enabled','created_by','approved_by','policy_id','source_id','actor_id','external_closed','frozen'}
    for name in names:
        model=getattr(m,name);table=model.__table__;columns=[c for c in table.columns if c.name in fields or c.name.endswith('_by')];stmt=select(*columns)
        if 'matter_id' in table.c:stmt=stmt.where(table.c.matter_id==matter)
        elif 'source_id' in table.c:stmt=stmt.where(table.c.source_id.in_(source_ids))
        if name=='Account':stmt=stmt.where(table.c.id.in_(subjects))
        if name=='Organization':stmt=stmt.where(table.c.id.in_(select(m.Account.organization_id).where(m.Account.id.in_(subjects))))
        if name=='Role':stmt=stmt.where(table.c.id.in_(select(m.RoleGrant.role_id).where(m.RoleGrant.account_id.in_(subjects))))
        if name in {'RoleGrant','MatterAssignment','EthicalWall','CleanTeamMembership'}:stmt=stmt.where(table.c.account_id.in_(subjects))
        if name in {'MatterAssignment','CleanTeamMembership'}:stmt=stmt.where(table.c.starts_at<=now,table.c.expires_at>now,table.c.revoked==False)
        if name in {'DisclosurePlan','SourceAccessGrant'}:stmt=stmt.where(table.c.expires_at>now)
        parts[name]=sorted([list(r) for r in db.execute(stmt)],key=canonical)
    policy_ids=select(m.DocumentPolicyVersion.id).where(m.DocumentPolicyVersion.matter_id==matter)
    from kestrel.services.documents import FIELDS
    parts['policies']=sorted([list(r) for r in db.execute(select(*[getattr(m.DocumentPolicyVersion,k) for k in [*FIELDS,'approved_snapshot_hash']]).where(m.DocumentPolicyVersion.matter_id==matter))],key=canonical)
    for model,key in [(m.PolicySource,'artifact_id'),(m.PolicyRecipient,'policy_id')]:parts[model.__tablename__]=sorted([list(r) for r in db.execute(select(*model.__table__.columns).where(getattr(model,key).in_(policy_ids)))],key=canonical)
    parts['wall_policies']=sorted([list(r) for r in db.execute(select(m.GovernanceVersion.id,m.GovernanceVersion.matter_id,m.GovernanceVersion.definition_json).where(m.GovernanceVersion.kind=='wall_policy',m.GovernanceVersion.state=='published',m.GovernanceVersion.matter_id==matter))],key=canonical)
    wall_stmt=text('SELECT id,client_id,matter_id,account_id,role_name,relationship_kind,entry_type FROM vw_person_wall_entries WHERE starts_at<=:now AND (expires_at IS NULL OR expires_at>:now) AND (account_id IS NULL OR account_id IN :subjects) AND (matter_id=:matter OR (matter_id IS NULL AND client_id=:client))').bindparams(bindparam('subjects',expanding=True))
    parts['person_walls']=sorted([list(r) for r in db.execute(wall_stmt,{'now':now,'subjects':sorted(subjects),'matter':matter,'client':client_id})],key=canonical)
    return digest(canonical(parts).encode())

def begin(db,request,matter):
    before=authorization_inputs(db,matter,authenticate(db,request)[2].id);db.expire_all();actor=authenticate(db,request)[2];q.access(actor,matter,db)
    return before,actor

def finish(db,request,matter,before):
    db.expire_all();actor=authenticate(db,request)[2];q.access(actor,matter,db)
    if authorization_inputs(db,matter,actor.id)!=before:raise HTTPException(409,'Authorization inputs changed while preparing this table or export; refresh before retrying')
    return actor

def throttle(actor):
    now=time.monotonic()
    with _lock:
        for uid in list(_requests):
            if not _requests[uid] or _requests[uid][-1]<now-60:del _requests[uid]
        queue=_requests.setdefault(actor.id,deque())
        while queue and queue[0]<now-60:queue.popleft()
        if len(queue)>=60:raise HTTPException(429,'Table request limit reached; wait before retrying')
        queue.append(now)

def inventory(db,actor,matter,filters,ids=None):
    q.access(actor,matter,db)
    stmt=select(*[getattr(m.SourceVersion,k) for k in SOURCE_FIELDS],m.DocumentPolicyVersion).join(m.DocumentPolicyVersion,m.SourceVersion.policy_id==m.DocumentPolicyVersion.id).where(m.SourceVersion.matter_id==matter)
    if not filters.historical:stmt=stmt.where(m.DocumentPolicyVersion.superseded==False)
    if filters.contracts_only:stmt=stmt.where(m.DocumentPolicyVersion.resource_type.in_(['contract','licence']))
    if ids is not None:stmt=stmt.where(m.SourceVersion.id.in_(ids))
    for key in ['language','wave']:
        value=getattr(filters,key)
        if value:stmt=stmt.where(getattr(m.SourceVersion,key)==value)
    if filters.classification:stmt=stmt.where(m.DocumentPolicyVersion.classification==filters.classification)
    rows=[]
    for record in db.execute(stmt.order_by(m.SourceVersion.created_at,m.SourceVersion.id)):
        policy=record[-1]
        try:w.require_policy(db,actor,policy,'historical_read' if policy.superseded else 'read' if policy.classification_confirmed else 'triage')
        except HTTPException as e:
            if e.status_code!=403:raise
            continue
        value={key:record[i] for i,key in enumerate(SOURCE_FIELDS)}
        value.update({'classification':policy.classification,'classification_confirmed':policy.classification_confirmed,'resource_type':policy.resource_type})
        rows.append((value,policy))
    return rows

def collect(db,actor,view,p):
    if view=='findings':
        if any(v is not None for v in [p.source_filters,p.financial_filters,p.task_filters]):raise HTTPException(422,'Only finding filters can be applied to findings')
        from kestrel.services import finding_tables
        return finding_tables.collect(db,actor,p.matter_id,p.finding_filters)
    if p.finding_filters is not None:raise HTTPException(422,'Finding filters cannot be applied to this dataset')
    if view=='tasks':
        if p.source_filters is not None or p.financial_filters is not None:raise HTTPException(422,'Only task filters can be applied to tasks')
        from kestrel.services import task_tables
        return task_tables.collect(db,actor,p.matter_id,p.task_filters)
    if p.task_filters is not None:raise HTTPException(422,'Task filters cannot be applied to this dataset')
    if view=='inventory':
        if p.financial_filters is not None:raise HTTPException(422,'Financial filters cannot be applied to inventory')
        return inventory(db,actor,p.matter_id,p.source_filters or Sources())
    if p.source_filters is not None:raise HTTPException(422,'Source filters cannot be applied to financial facts')
    value=f.query(db,actor,Query(matter_id=p.matter_id,**(p.financial_filters.model_dump() if p.financial_filters else {})),view_action='table.financial.scope_scan')
    if value['truncated']:raise HTTPException(413,'Financial table baseline is limited to 100 permitted matching facts; narrow the typed entity, metric, period or currency filters')
    return [(row,None) for row in value['rows']]

def query(db,actor,view,p,request):
    throttle(actor);q.access(actor,p.matter_id,db)
    saved_id=p.saved_view_id;saved_hash=None;matter=p.matter_id;draw=p.draw;start=p.start
    before,actor=begin(db,request,matter)
    if view in {'tasks','findings'} and (p.saved_view_id is not None or p.saved_view_version_hash is not None):raise HTTPException(422,'Task and finding saved views require separately governed evidence support')
    if saved_id:
        from kestrel.services import table_views
        saved,saved_hash=table_views.resolve_selection(db,actor,saved_id,matter,view)
        if p.saved_view_version_hash is not None and p.saved_view_version_hash!=saved_hash:raise HTTPException(409,'Loaded saved configuration version changed; reload the view before querying')
        # Saved filters/order/page size are authoritative. Only transport draw and
        # page offset are live; editing the query must clear its saved-view ID.
        p=saved.model_copy(update={'draw':draw,'start':start})
    from kestrel.services import task_tables,finding_tables
    columns=INVENTORY_COLUMNS if view=='inventory' else task_tables.COLUMNS if view=='tasks' else finding_tables.COLUMNS if view=='findings' else FINANCIAL_COLUMNS
    sort=p.sort or ('file_name' if view=='inventory' else 'created_at' if view in {'tasks','findings'} else 'entity')
    if sort not in columns or set(p.column_filters)-set(columns):raise HTTPException(422,'Unknown table sort or column filter')
    records=collect(db,actor,view,p);total=len(records)
    scope_service=task_tables if view=='tasks' else finding_tables if view=='findings' else None
    scope_stamp=scope_service.signature(records) if scope_service else None
    needle=p.search.casefold()
    def matches(row):
        return (not needle or any(needle in str(row.get(k) if row.get(k) is not None else '').casefold() for k in columns)) and all(v.casefold() in str(row.get(k) if row.get(k) is not None else '').casefold() for k,v in p.column_filters.items())
    filtered=[pair for pair in records if matches(pair[0])]
    filtered.sort(key=lambda pair:(pair[0].get(sort) is None,(Decimal(pair[0][sort]) if sort=='amount_text' else pair[0][sort]) if pair[0].get(sort) is not None else '',pair[0]['id']),reverse=p.direction=='desc')
    page=filtered[p.start:p.start+p.length]
    actor=finish(db,request,p.matter_id,before)
    if scope_service and scope_service.signature(collect(db,actor,view,p))!=scope_stamp:raise HTTPException(409,'Retained history, source permissions or visible people changed while preparing the table; refresh before retrying')
    if saved_id:
        db.expire_all()
        _,current_hash=table_views.resolve_selection(db,actor,saved_id,matter,view)
        if current_hash!=saved_hash:raise HTTPException(409,'Saved configuration version changed while preparing the table; refresh before retrying')
    for row,policy in page:
        if view=='tasks':task_tables.event(db,actor,policy,'table.tasks.view')
        elif view=='findings':finding_tables.event(db,actor,policy,'table.findings.view')
        elif policy:w.event(db,actor,policy,'table.inventory.view',row['id'])
        else:w.event(db,actor,f.read(db,actor,db.get(m.FinancialFact,row['id']))[1],'table.financial.view',row['id'])
    db.commit();return {'draw':p.draw,'recordsTotal':total,'recordsFiltered':len(filtered),'data':[row for row,_ in page],'count_basis':'Current authorized matter and typed filters; totals exclude denied rows. Global and column search then determine filtered count.'}

def selected(db,actor,view,p):
    # External exports require a separately approved audience package, not this metadata tool.
    w.legal(actor,p.matter_id)
    if actor.org!=O.FIRM:raise HTTPException(403,'External exports require independently approved packages')
    if view=='findings':
        from kestrel.services import finding_tables
        from kestrel.schemas.data_tables import Findings
        if p.finding_versions is None or set(p.finding_versions)!=set(p.ids):raise HTTPException(422,'Finding exports require one exact revision ID for every selected finding')
        return finding_tables.collect(db,actor,p.matter_id,Findings(historical=p.historical),p.ids,export=True,versions=p.finding_versions)
    if p.finding_versions is not None:raise HTTPException(422,'Finding revision pins cannot be applied to this dataset')
    if view=='tasks':
        from kestrel.services import task_tables
        from kestrel.schemas.data_tables import Tasks
        return task_tables.collect(db,actor,p.matter_id,Tasks(historical=p.historical),p.ids,export=True)
    if view=='inventory':
        permitted=[]
        for row,policy in inventory(db,actor,p.matter_id,Sources(historical=p.historical),p.ids):
            try:w.require_policy(db,actor,policy,'export_metadata');permitted.append((row,policy))
            except HTTPException as error:
                if error.status_code!=403:raise
        return permitted
    rows=[]
    for fid in p.ids:
        row=db.get(m.FinancialFact,fid)
        if not row or row.matter_id!=p.matter_id:continue
        try:
            _,policy,_=f.read(db,actor,row);w.require_policy(db,actor,policy,'export_metadata');rows.append((f.output(db,actor,row,view_action='table.financial.export_prepare'),policy))
        except HTTPException as error:
            if error.status_code not in {403,404,409}:raise
    return rows

def export(db,actor,view,p,request):
    from kestrel.services import task_tables,finding_tables
    throttle(actor);w.legal(actor,p.matter_id);before,actor=begin(db,request,p.matter_id);rows=selected(db,actor,view,p);fields=INVENTORY_COLUMNS if view=='inventory' else task_tables.COLUMNS if view=='tasks' else finding_tables.COLUMNS if view=='findings' else FINANCIAL_COLUMNS
    scope_service=task_tables if view=='tasks' else finding_tables if view=='findings' else None
    scope_stamp=scope_service.signature(rows) if scope_service else None
    if p.format=='csv':
        out=io.StringIO();writer=csv.writer(out);writer.writerow(fields)
        for row,_ in rows:
            values=[str(row.get(k) if row.get(k) is not None else '') for k in fields];writer.writerow(["'"+v if v[:1] in '=+-@\t\r' else v for v in values])
        data=out.getvalue().encode('utf-8');media='text/csv; charset=utf-8'
    else:
        from openpyxl import Workbook
        book=Workbook();sheet=book.active;sheet.title='Inventory' if view=='inventory' else 'Tasks' if view=='tasks' else 'Findings' if view=='findings' else 'Financial facts';sheet.append(fields)
        for row,_ in rows:
            sheet.append([str(row.get(k) if row.get(k) is not None else '') for k in fields])
            for cell in sheet[sheet.max_row]:cell.data_type='s'
        sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
        out=io.BytesIO();book.save(out);book.close();data=out.getvalue();media='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    actor=finish(db,request,p.matter_id,before)
    if scope_service and scope_service.signature(selected(db,actor,view,p))!=scope_stamp:raise HTTPException(409,'Retained history, source permissions or visible people changed while preparing the export; refresh before retrying')
    for row,policy in rows:
        if view=='tasks':task_tables.event(db,actor,policy,'table.tasks.metadata_export')
        elif view=='findings':finding_tables.event(db,actor,policy,'table.findings.metadata_export')
        else:w.event(db,actor,policy,'table.'+view+'.metadata_export',row['id'])
    from kestrel.services.auth import audit
    unavailable=len(p.ids)-len(rows)
    audit(db,'table.'+view+('.export_partial' if unavailable else '.export_complete'),'partial' if unavailable else 'allowed',actor.id,category='access',matter_id=p.matter_id)
    db.commit();return data,media,{'Content-Disposition':'attachment; filename="kestrel-'+view+'-internal.'+p.format+'"','X-Export-Unavailable-Count':str(len(p.ids)-len(rows)),'X-Content-SHA256':hashlib.sha256(data).hexdigest(),'Cache-Control':'no-store'}
