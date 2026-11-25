"""One bounded permitted baseline for audit paging and matching exports."""
import io
import json
import zipfile
from fastapi import HTTPException
from sqlalchemy import select
from kestrel import models as m
from kestrel.adapters.extraction import canonical,digest
from kestrel.services import auth,auditing

COUNT_BASIS='Currently permitted events in the applied category/matter/time window; maximum 1000 before text filtering.'


def capture(db,request,actor_id):
    db.expire_all();identity=auth.authenticate(db,request);actor=identity[2]
    if actor.id!=actor_id:raise HTTPException(403,'Identity changed during audit request')
    return actor,authority_inputs(db,actor,identity[1])


def authority_inputs(db,actor,session):
    """Metadata-only change detector, never a permission decision.

    Include all currently allowed matters because an audit object's retained
    lineage can cross the explicit event-matter filter. This conservative local
    prototype can retry on an unrelated security change; its cost is unmeasured.
    No passage, rationale, profile payload, credential or raw clock is retained.
    """
    from kestrel.services.data_tables import authorization_inputs
    from kestrel.services.content_labels import checked as checked_labels
    now=auth.clock();matters=sorted(actor.matters-actor.walls)
    def rows(model,fields,*conditions):
        return sorted([list(row) for row in db.execute(select(*[getattr(model,key) for key in fields]).where(*conditions))],key=canonical)
    parts={'principal':{'id':actor.id,'org':actor.org.value,'roles':sorted(actor.roles),
        'matters':sorted(actor.matters),'walls':sorted(actor.walls),'client_walls':sorted(actor.client_walls)},
        'session':[session.id,session.account_id,session.host,session.expires_at,session.revoked,session.expires_at>now],
        'matters':[(matter,authorization_inputs(db,matter,actor.id)) for matter in matters]}
    parts['account']=rows(m.Account,['id','organization_id','active'],m.Account.id==actor.id)
    parts['organization']=rows(m.Organization,['id','code'],m.Organization.id.in_(select(m.Account.organization_id).where(m.Account.id==actor.id)))
    parts['roles']=rows(m.Role,['id','name'],m.Role.id.in_(select(m.RoleGrant.role_id).where(m.RoleGrant.account_id==actor.id)))
    parts['role_grants']=rows(m.RoleGrant,['id','account_id','role_id'],m.RoleGrant.account_id==actor.id)
    parts['walls']=rows(m.EthicalWall,['id','account_id','matter_id','active'],m.EthicalWall.account_id==actor.id)
    for model,fields in [(m.MatterAssignment,['id','account_id','matter_id','starts_at','expires_at','revoked']),
            (m.CleanTeamMembership,['id','account_id','matter_id','scope','approved_by','starts_at','expires_at','revoked'])]:
        values=rows(model,fields,model.account_id==actor.id)
        start,end,revoked=(fields.index(key) for key in ['starts_at','expires_at','revoked'])
        parts[model.__tablename__]=[value+[value[start]<=now<value[end] and not value[revoked]] for value in values]
    # Catch appended sibling/task history as well as captured restriction edits.
    # Foreign keys preserve the resolver relationships without hashing bodies.
    for mapper in sorted(m.Base.registry.mappers,key=lambda item:item.local_table.name):
        model=mapper.class_
        if not issubclass(model,m.SourceWorkScope):continue
        fields=[column.name for column in mapper.local_table.columns
            if column.name in {'id','retained_classification','retained_scope'} or column.name.endswith('_id')]
        parts[mapper.local_table.name]=rows(model,fields,model.matter_id.in_(matters))
    parts['source_identity']=rows(m.SourceVersion,['id','matter_id','policy_id','previous_id','bytes_hash','text_hash','extraction_status','extractor_version'],m.SourceVersion.matter_id.in_(matters))
    label_fields=['id','labels_json','label_scope','version_number','unit_number','start_offset','end_offset','evidence_hash',
        'source_bytes_hash','source_text_hash','provenance_kind','classifier_version','confidence','content_hash','created_by','created_at']
    labels=rows(m.ContentLabelAssertion,label_fields,m.ContentLabelAssertion.matter_id.in_(matters))
    try:
        for value in labels:
            assertion=db.get(m.ContentLabelAssertion,value[0])
            if assertion is None:raise ValueError()
            # Existing integrity validator verifies the retained body/hash.
            # Only safe label drivers enter our receipt; no rationale is kept.
            parsed,_=checked_labels(db,assertion)
            value[1]=parsed
        parts['label_drivers']=labels
        parts['label_decisions']=rows(m.ContentLabelDecision,['id','assertion_id','sequence','operation','content_hash'],m.ContentLabelDecision.matter_id.in_(matters))
        versions=select(m.ChecklistVersion.id).where(m.ChecklistVersion.matter_id.in_(matters))
        checklist=rows(m.ChecklistCoverageDecision,['id','version_id','source_ids_json','source_snapshots_json'],m.ChecklistCoverageDecision.version_id.in_(versions))
        for value in checklist:
            source_ids=json.loads(value[2]);snapshots=json.loads(value[3])
            if not isinstance(source_ids,list) or any(not isinstance(key,str) for key in source_ids) or not isinstance(snapshots,dict):raise ValueError()
            restrictions=snapshots.get('_restrictions',[])
            if not isinstance(restrictions,list):raise ValueError()
            retained=[]
            for item in restrictions:
                if not isinstance(item,dict) or not isinstance(item.get('matter_id'),str) or not item['matter_id'] or item.get('classification') not in {'ordinary','privileged','clean_team'} or not (item.get('clean_team_scope') is None or isinstance(item.get('clean_team_scope'),str)):raise ValueError()
                if item['classification']=='clean_team' and not (item.get('clean_team_scope') or '').strip():raise ValueError()
                retained.append({key:item.get(key) for key in ['matter_id','classification','clean_team_scope']})
            value[2]=source_ids;value[3]=retained
        parts['checklist_restrictions']=checklist
    except (ValueError,TypeError,KeyError):
        raise HTTPException(409,'Audit authorization metadata is indeterminate; output withheld') from None
    return digest(canonical(parts).encode())


def baseline(db,actor,filters):
    # The existing selector applies own/granted/named/retained restrictions and
    # rejects the 1001st permitted event before any literal grid search.
    return auditing.selected(db,actor,filters.category,filters.matter_id,limit=1000,
        from_time=filters.from_time,to_time=filters.to_time)


def object_inputs(db,prepared):
    """Bounded closure of the actual prepared audit objects, without content.

    Resolve through the existing canonical retained-record resolver rather than
    duplicating its container-FK graph. Fallback mappings mirror selected()'s
    direct policy/source/report resolution; they detect changes, never permit.
    """
    from kestrel.services.review_work import audit_records
    parts=[]
    try:
        for key in sorted({row['object_id'] for row in prepared if row['object_id']}):
            records=[];bindings=[]
            for row in audit_records(db,key):
                records.append([type(row).__name__,row.id,row.matter_id,row.source_id,row.retained_classification,row.retained_scope])
            if db.scalar(select(m.DocumentPolicyVersion.id).where(m.DocumentPolicyVersion.id==key)):
                bindings.append(['policy',key,key])
            for model in [m.SourceVersion,m.SourceFinding,m.LegalFindingRevision,m.ReleasePackage,m.ClientSubmission]:
                policy_id=db.scalar(select(model.policy_id).where(model.id==key))
                if policy_id:bindings.append([model.__tablename__,key,policy_id])
            for model,field in [(m.AnalysisJob,'document_version_id'),(m.OCRJob,'source_id'),(m.SourceAccessGrant,'source_id')]:
                source_id=db.scalar(select(getattr(model,field)).where(model.id==key))
                if source_id:
                    policy_id=db.scalar(select(m.SourceVersion.policy_id).where(m.SourceVersion.id==source_id))
                    bindings.append([model.__tablename__,key,source_id,policy_id])
            for model in [m.ReportVersion,m.CollaborationMessage]:
                release_id=db.scalar(select(model.release_id).where(model.id==key))
                if release_id:
                    policy_id=db.scalar(select(m.ReleasePackage.policy_id).where(m.ReleasePackage.id==release_id))
                    bindings.append([model.__tablename__,key,release_id,policy_id])
            parts.append([key,sorted(records,key=canonical),sorted(bindings,key=canonical)])
    except (ValueError,TypeError,KeyError,AttributeError):
        raise HTTPException(409,'Audit retained-reference metadata is indeterminate; output withheld') from None
    return digest(canonical(parts).encode())


def checked(db,request,actor_id,filters,prepared,before,objects):
    actor,current_inputs=capture(db,request,actor_id)
    if current_inputs!=before or object_inputs(db,prepared)!=objects:raise HTTPException(409,'Audit authorization changed while preparing response; retry with current access')
    current=baseline(db,actor,filters)
    actor,after=capture(db,request,actor_id)
    if after!=before or object_inputs(db,prepared)!=objects or current!=prepared:raise HTTPException(409,'Audit selection or authorization changed while preparing response; retry with current access')
    return actor


def filtered(rows,payload):
    def text(value):return '' if value is None else str(value).casefold()
    search=payload.search.casefold()
    columns={key:value.casefold() for key,value in payload.column_filters.items() if value}
    result=[row for row in rows if (not search or any(search in text(row[key]) for key in auditing.FIELDS))
        and all(value in text(row[key]) for key,value in columns.items())]
    # Stable ID tie order, independent of requested primary direction.
    result.sort(key=lambda row:row['id'])
    result.sort(key=lambda row:(row[payload.sort] is not None,
        row[payload.sort] if payload.sort=='occurred_at' else text(row[payload.sort])),reverse=payload.direction=='desc')
    return result


def query(db,actor,request,payload):
    try:
        current,before=capture(db,request,actor.id);rows=baseline(db,current,payload.audit_filters)
        objects=object_inputs(db,rows)
        matches=filtered(rows,payload)
        result={'draw':payload.draw,'recordsTotal':len(rows),'recordsFiltered':len(matches),
                'data':matches[payload.start:payload.start+payload.length],'count_basis':COUNT_BASIS}
        checked(db,request,actor.id,payload.audit_filters,rows,before,objects)
        return result
    except HTTPException:
        db.rollback();raise


def events(db,actor,request,filters):
    try:
        current,before=capture(db,request,actor.id);rows=baseline(db,current,filters)
        objects=object_inputs(db,rows)
        checked(db,request,actor.id,filters,rows,before,objects);return rows
    except HTTPException:
        db.rollback();raise


def export(db,actor,request,filters,format,*,payload=None):
    try:
        current,before=capture(db,request,actor.id);rows=baseline(db,current,filters)
        objects=object_inputs(db,rows)
        matches=filtered(rows,payload) if payload is not None else rows
        descriptor=({'audit_filters':filters.model_dump(),'search':payload.search,
            'column_filters':payload.column_filters,'sort':payload.sort,'direction':payload.direction,
            'selection':'all_filtered'} if payload is not None else
            {'category':filters.category,'matter_id':filters.matter_id,'from_time':filters.from_time,'to_time':filters.to_time})
        data,_,manifest=auditing.render(matches,format,current,descriptor)
        checked(db,request,actor.id,filters,rows,before,objects)
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('events.'+format,data)
            archive.writestr('manifest.json',json.dumps(manifest,sort_keys=True))
        checked(db,request,actor.id,filters,rows,before,objects)
        # Export receipts are appended only after every compared selection.
        # Query/events reads deliberately do not audit their own selection.
        if filters.category=='clean_team':
            for matter,scope in {(row['matter_id'],row['clean_team_scope']) for row in matches}:
                auth.audit(db,'audit.export','allowed',actor.id,category=filters.category,matter_id=matter,clean_team_scope=scope)
        else:auth.audit(db,'audit.export','allowed',actor.id,category=filters.category,matter_id=filters.matter_id)
        db.commit();return output.getvalue()
    except HTTPException:
        db.rollback();raise
