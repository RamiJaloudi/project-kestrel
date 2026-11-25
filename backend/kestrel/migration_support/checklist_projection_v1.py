"""Additive projection contract v1. Explicit SQL columns; no mutable application models."""
import hashlib,json
from uuid import uuid5,NAMESPACE_URL
from sqlalchemy import text

def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def stable(value):return str(uuid5(NAMESPACE_URL,'kestrel:checklist-projection-v1:'+value))

def ensure(connection,table,values):
    # All table/column identifiers are internal constants, never vendor input.
    old=connection.execute(text('SELECT '+','.join(values)+' FROM '+table+' WHERE id=:id'),{'id':values['id']}).mappings().first()
    if old:
        if dict(old)!=values:raise RuntimeError('Checklist projection integrity mismatch')
        return
    connection.execute(text('INSERT INTO '+table+'('+','.join(values)+') VALUES ('+','.join(':'+k for k in values)+')'),values)

def project_version(connection,version_id):
    row=connection.execute(text('SELECT id,matter_id,definition_json FROM checklist_versions WHERE id=:id'),{'id':version_id}).mappings().one()
    definition=json.loads(row['definition_json'])
    for section in definition['sections']:
        ensure(connection,'checklist_sections',{'id':stable('section:'+row['id']+':'+section['section_code']),'matter_id':row['matter_id'],'version_id':row['id'],
            'section_code':section['section_code'],'title':section['title'],'page_start':section['page_start'],'page_end':section['page_end']})
    for item in definition['items']:
        ensure(connection,'checklist_items',{'id':stable('item:'+row['id']+':'+item['item_id']),'matter_id':row['matter_id'],'version_id':row['id'],
            'section_id':stable('section:'+row['id']+':'+item['section_code']),'item_code':item['item_id'],'short_abstract':item['short_abstract'],
            'source_page':item['source_page'],'definition_hash':hashlib.sha256(encoded(item).encode()).hexdigest()})

def project_coverage(connection,event_id):
    event=connection.execute(text('SELECT * FROM checklist_coverage_decisions WHERE id=:id'),{'id':event_id}).mappings().one()
    version=connection.execute(text('SELECT matter_id FROM checklist_versions WHERE id=:id'),{'id':event['version_id']}).scalar_one()
    item_id=stable('item:'+event['version_id']+':'+event['item_id'])
    ensure(connection,'checklist_coverage_versions',{'id':stable('coverage:'+event_id),'coverage_event_id':event_id,'matter_id':version,'item_id':item_id,
        'revision':event['revision'],'status':event['status'],'kind':event['kind'],'actor_id':event['actor_id'],'created_at':event['created_at']})
    for sid in json.loads(event['source_ids_json']):
        source=connection.execute(text('SELECT matter_id,bytes_hash FROM source_versions WHERE id=:id'),{'id':sid}).mappings().one()
        if source['matter_id']!=version:raise RuntimeError('Cross-matter checklist projection rejected')
        ensure(connection,'document_checklist_links',{'id':stable('source:'+event_id+':'+sid),'matter_id':version,'coverage_event_id':event_id,'item_id':item_id,'source_id':sid,'bytes_hash':source['bytes_hash']})
    snapshots=json.loads(event['source_snapshots_json'])
    for key in json.loads(event['finding_ids_json']):
        rid=snapshots['finding:'+key]['revision_id']
        revision=connection.execute(text('SELECT id FROM legal_finding_revisions WHERE id=:id'),{'id':rid}).scalar()
        candidate=connection.execute(text('SELECT id FROM source_findings WHERE id=:id'),{'id':rid}).scalar() if not revision else None
        if not revision and not candidate:raise RuntimeError('Missing retained finding revision')
        ensure(connection,'checklist_finding_links',{'id':stable('finding:'+event_id+':'+key),'matter_id':version,'coverage_event_id':event_id,'item_id':item_id,'finding_reference':key,'candidate_id':candidate,'revision_id':revision})

def backfill(connection):
    for key in list(connection.execute(text('SELECT id FROM checklist_versions ORDER BY id')).scalars()):project_version(connection,key)
    for key in list(connection.execute(text('SELECT id FROM checklist_coverage_decisions ORDER BY version_id,item_id,revision')).scalars()):project_coverage(connection,key)
