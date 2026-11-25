"""Comparison is a collection of independent reads, never a new access grant."""
import json
from sqlalchemy import select,or_,and_
from fastapi import HTTPException
from kestrel import models as m
from kestrel.services import questions as q,workflow as w,disclosures as d
from kestrel.adapters.citation_anchors import anchors
from kestrel.services.auth import audit

def resource(db,actor,kind,rid,historical=False):
    if kind=='source':
        row,policy=w.source(db,actor,rid,historical);w.source_integrity(row,policy)
        return row,policy,json.loads(row.units_json),row.file_name,row.version_number
    row,policy=d.read(db,actor,rid);plan,_=d.integrity(db,row)
    return row,policy,json.loads(row.units_json),plan.title,1

def candidates(db,actor,matter,kind,historical,search,limit,after,request):
    q.access(actor,matter,db)
    from kestrel.services.data_tables import begin,finish
    before,actor=begin(db,request,matter)
    model=m.SourceVersion if kind=='source' else m.DisclosureArtifact
    stmt=select(model).where(model.matter_id==matter)
    if kind=='source':
        stmt=stmt.join(m.DocumentPolicyVersion,model.policy_id==m.DocumentPolicyVersion.id)
        if not historical:stmt=stmt.where(m.DocumentPolicyVersion.superseded==False)
        if search:stmt=stmt.where(or_(model.file_name.ilike('%'+search+'%'),model.logical_key.ilike('%'+search+'%')))
    elif search:stmt=stmt.join(m.DisclosurePlan,model.plan_id==m.DisclosurePlan.id).where(m.DisclosurePlan.title.ilike('%'+search+'%'))
    if after:
        try:
            cursor,_,_,_,_=resource(db,actor,kind,after,historical)
            if cursor.matter_id!=matter:raise HTTPException(404,'Cursor unavailable')
        except HTTPException:raise HTTPException(404,'Cursor unavailable; refresh permitted candidates')
        stmt=stmt.where(or_(model.created_at>cursor.created_at,and_(model.created_at==cursor.created_at,model.id>cursor.id)))
    rows=[];more=False
    for item in db.scalars(stmt.order_by(model.created_at,model.id)):
        try:
            row,policy,_,title,version=resource(db,actor,kind,item.id,historical)
            if len(rows)==limit:more=True;break
            rows.append({'id':row.id,'kind':kind,'title':title,'version_number':version,'target':{'id':row.id,'historical':historical,**({'kind':'disclosure'} if kind=='derivative' else {})}})
        except HTTPException as e:
            if e.status_code!=403:raise
    finish(db,request,matter,before)
    return {'rows':rows,'has_more':more,'next_after':rows[-1]['id'] if more and rows else None,'count_basis':'this permitted page only; no global or denied-resource count'}

def compare(db,actor,p,request):
    q.access(actor,p.matter_id,db);panes=[]
    from kestrel.services.data_tables import begin,finish
    before,actor=begin(db,request,p.matter_id)
    for i,target in enumerate(p.targets):
        try:
            row,policy,units,title,version=resource(db,actor,target.kind,target.id,target.historical)
            if row.matter_id!=p.matter_id:raise HTTPException(403,'Selected matter denied')
            location={}
            if target.unit is not None:
                unit=next((u for u in units if u['number']==target.unit),None)
                if not unit or (target.end is not None and target.end>len(unit['text'])):raise HTTPException(409,'Citation location unavailable')
                location={'unit':target.unit,**({'start':target.start,'end':target.end} if target.start is not None else {})}
            w.event(db,actor,policy,'reader.comparison_preflight',row.id)
            panes.append({'index':i,'allowed':True,'title':title,'version_number':version,'target':{'id':row.id,'historical':target.historical,**location,**({'kind':'disclosure'} if target.kind=='derivative' else {})},
                'citation_anchors':anchors(units,source_id=row.id if target.kind=='source' else None,artifact_id=row.id if target.kind=='derivative' else None)})
        except HTTPException as e:
            if e.status_code not in {403,404,409}:raise
            audit(db,'reader.comparison.denied','denied',actor.id,category='access')
            panes.append({'index':i,'allowed':False,'message':'Pane unavailable in your current permissions or version state'})
    finish(db,request,p.matter_id,before)
    db.commit();return {'panes':panes,'alignment':'Independent document coordinates; no line, page or financial equivalence is inferred'}
