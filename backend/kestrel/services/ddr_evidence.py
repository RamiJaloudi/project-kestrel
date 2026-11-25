"""Reviewed-only graph evidence: protected content stays outside checkpoints."""
import json
from fastapi import HTTPException
from kestrel import models as m
from kestrel.services import workflow as w,diligence
from kestrel.adapters.extraction import canonical,digest


def capture(db,actor,matter,finding_ids,*,external_processing=False):
    w.legal(actor,matter)
    if not 1<=len(finding_ids)<=30 or len(set(finding_ids))!=len(finding_ids):raise HTTPException(422,'One to thirty distinct reviewed finding references required')
    items=[];content=[]
    for key in sorted(finding_ids):
        finding,policy=diligence.resolve(db,actor,key)
        source,source_policy=w.source(db,actor,finding.source_id)
        if source.matter_id!=matter or policy.matter_id!=matter:raise HTTPException(403,'Evidence outside run scope')
        if policy.review_state!='reviewed' or not source_policy.classification_confirmed:raise HTTPException(409,'Confirmed source and lawyer-reviewed finding required')
        if source_policy.superseded or source_policy.signing_frozen:raise HTTPException(409,'Current unfrozen evidence required')
        for p in [source_policy,policy]:
            w.require_policy(db,actor,p,'analyze');w.processing_allowed(db,p,external=external_processing)
        w.source_integrity(source,source_policy);w.require_verified_ocr(db,source)
        units={u['number']:u for u in json.loads(source.units_json)}
        spans=json.loads(finding.evidence_json);opaque=[]
        if not spans or len(spans)>30:raise HTTPException(409,'Bounded exact source evidence required')
        for span in spans:
            unit=units.get(span.get('unit'));start=span.get('start');end=span.get('end');quote=span.get('quote')
            if not unit or type(start) is not int or type(end) is not int or not isinstance(quote,str) or not quote or not 0<=start<end<=len(unit['text']) or unit['text'][start:end]!=quote:raise HTTPException(409,'Original-language evidence integrity failed')
            opaque.append({'unit':span['unit'],'start':start,'end':end,'quote_hash':digest(quote.encode())})
        reviewed=diligence.output(db,finding,policy)
        item={'finding_id':key,'revision_id':finding.id,'source_id':source.id,'bytes_hash':source.bytes_hash,'text_hash':source.text_hash,
            'source_snapshot':w.snapshot(db,source_policy),'finding_snapshot':w.snapshot(db,policy),
            'reviewed_content_hash':digest(canonical({k:reviewed[k] for k in ['summary','reviewer_id','severity','materiality','exposure','workflow_status','action','rationale']}).encode()),
            'language':source.language,'governing_law':source.governing_law,'playbook_id':reviewed['playbook_id'],'playbook_hash':reviewed['playbook_hash'],
            'model_config_hash':digest(reviewed['model_config'].encode()),'taxonomy_version':reviewed['taxonomy_version'],'evidence':opaque}
        items.append(item);content.append({'finding_id':key,'revision_id':finding.id,'summary':reviewed['summary'],'severity':reviewed['severity'],
            'materiality':reviewed['materiality'],'action':reviewed['action'],'evidence':spans})
    snapshot={'schema':'ddr-reviewed-evidence-1','matter_id':matter,'external_processing':external_processing,'items':items}
    return {'hash':digest(canonical(snapshot).encode()),'snapshot':snapshot,'content':content}


def validate(db,actor,snapshot):
    if not isinstance(snapshot,dict) or snapshot.get('schema')!='ddr-reviewed-evidence-1' or type(snapshot.get('external_processing')) is not bool:raise HTTPException(409,'Invalid evidence snapshot')
    try:keys=[item['finding_id'] for item in snapshot['items']]
    except (KeyError,TypeError):raise HTTPException(409,'Invalid evidence snapshot')
    fresh=capture(db,actor,snapshot.get('matter_id'),keys,external_processing=snapshot['external_processing'])
    if canonical(fresh['snapshot'])!=canonical(snapshot):raise HTTPException(409,'Reviewed evidence changed; a separately authorized new run is required')
    return fresh
