import hashlib
import json
import re
from fastapi import HTTPException
from sqlalchemy import select,update
from kestrel.models import GovernanceVersion
from kestrel.domain import Role as R,Organization as O,member_and_not_walled
from kestrel.services.auth import audit

APPROVER={'legal_playbook':R.SME,'environment_policy':R.SECURITY,'wall_policy':R.CONFLICTS}


def definition(value):
    encoded=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
    if len(encoded)>64000:raise HTTPException(413,'Definition too large')
    return encoded,hashlib.sha256(encoded.encode()).hexdigest()


def access(actor,matter):
    if actor.org!=O.FIRM or not member_and_not_walled(actor,matter):raise HTTPException(403,'Governance scope denied')


def read(db,actor,version):
    row=db.get(GovernanceVersion,version)
    if row is None:raise HTTPException(404,'Version unavailable')
    access(actor,row.matter_id)
    if not actor.roles & {R.ROOT_ADMIN,R.SME,R.SECURITY,R.CONFLICTS}:raise HTTPException(403,'Governance role required')
    return row


def create(db,actor,payload):
    access(actor,payload.matter_id)
    if payload.kind=='legal_playbook':
        from kestrel.services.lifecycle import mutable
        mutable(db,payload.matter_id)
    if payload.kind not in APPROVER:raise HTTPException(422,'Unknown definition kind')
    if not actor.roles & {R.ROOT_ADMIN,APPROVER[payload.kind]}:raise HTTPException(403,'Draft role required')
    validate_definition(payload.kind,payload.definition)
    base_id=getattr(payload,'base_playbook_id',None)
    if payload.kind=='legal_playbook' and not base_id and db.scalar(select(GovernanceVersion.id).where(GovernanceVersion.matter_id==payload.matter_id,GovernanceVersion.kind=='legal_playbook',GovernanceVersion.name==payload.name,GovernanceVersion.state=='published')):
        raise HTTPException(409,'A published playbook already has this name; select it as the replacement base')
    if base_id:
        base=read(db,actor,base_id)
        if payload.kind!='legal_playbook' or base.kind!='legal_playbook' or base.state!='published' or base.matter_id!=payload.matter_id:raise HTTPException(409,'Published same-matter legal playbook base required')
    encoded,digest=definition(payload.definition)
    row=GovernanceVersion(matter_id=payload.matter_id,author_id=actor.id,kind=payload.kind,name=payload.name,
        definition_json=encoded,content_hash=digest,base_playbook_id=base_id)
    db.add(row);db.flush()
    audit(db,'governance.draft','created',actor.id,category='legal_sme' if row.kind=='legal_playbook' else 'administrative',matter_id=row.matter_id,object_id=row.id)
    db.commit();return row


def transition(db,actor,row,operation,expected_revision,rationale):
    access(actor,row.matter_id)
    if row.kind=='legal_playbook':
        from kestrel.services.lifecycle import mutable
        mutable(db,row.matter_id)
    if definition(json.loads(row.definition_json))[1]!=row.content_hash:raise HTTPException(409,'Definition integrity check failed')
    if operation=='submit':
        if row.state!='draft' or actor.id!=row.author_id:raise HTTPException(403,'Draft author submission required')
        target='submitted'
    elif operation in {'approve','reject'}:
        if row.state!='submitted':raise HTTPException(409,'Submitted version required')
        if actor.id==row.author_id or APPROVER[row.kind] not in actor.roles:raise HTTPException(403,'Independent scoped approver required')
        if operation=='approve' and row.kind=='legal_playbook' and row.tested_hash!=row.content_hash:
            raise HTTPException(409,'Passing tests for this exact definition required')
        target='approved' if operation=='approve' else 'rejected'
    elif operation=='publish':
        if R.ROOT_ADMIN not in actor.roles and actor.id!=row.author_id:raise HTTPException(403,'Publisher role required')
        if row.state!='approved' or row.approved_hash!=row.content_hash:raise HTTPException(409,'Exact approved version required')
        target='published'
    else:raise HTTPException(422,'Unknown transition')
    if operation=='publish' and row.kind=='legal_playbook':
        from kestrel.services.action_center import publication
        publication(db,row)
    result=db.execute(update(GovernanceVersion).where(GovernanceVersion.id==row.id,
        GovernanceVersion.revision==expected_revision,GovernanceVersion.state==row.state).values(state=target,revision=expected_revision+1))
    if result.rowcount!=1:raise HTTPException(409,'Stale version; refresh')
    if operation in {'approve','reject'}:
        row.reviewer_id=actor.id;row.review_rationale=rationale
        row.approved_hash=row.content_hash if operation=='approve' else None
    audit(db,'governance.'+operation,'allowed',actor.id,category='legal_sme' if row.kind=='legal_playbook' else 'administrative',matter_id=row.matter_id,object_id=row.id)
    db.commit();return row


def edit(db,actor,row,value,expected_revision):
    if row.kind=='legal_playbook':
        from kestrel.services.lifecycle import mutable
        mutable(db,row.matter_id)
    if row.state!='draft' or actor.id!=row.author_id:raise HTTPException(403,'Editable own draft required; duplicate another author draft')
    validate_definition(row.kind,value)
    encoded,digest=definition(value)
    result=db.execute(update(GovernanceVersion).where(GovernanceVersion.id==row.id,GovernanceVersion.state=='draft',
        GovernanceVersion.revision==expected_revision).values(definition_json=encoded,content_hash=digest,tested_hash=None,revision=expected_revision+1))
    if result.rowcount!=1:raise HTTPException(409,'Stale version; refresh')
    # Technical edits must not retain someone else's author identity for self-approval checks.
    row.author_id=actor.id
    audit(db,'governance.edit','allowed',actor.id,category='legal_sme' if row.kind=='legal_playbook' else 'administrative',matter_id=row.matter_id,object_id=row.id)
    db.commit();return row


def validate_definition(kind,value):
    if kind=='environment_policy':
        if set(value)!={'block_ai','block_cloud','block_external','allowed_regions'}:raise HTTPException(422,'Explicit environment fields required')
        if any(type(value[k]) is not bool for k in ['block_ai','block_cloud','block_external']):raise HTTPException(422,'Boolean restrictions required')
        if not isinstance(value['allowed_regions'],list) or not value['allowed_regions'] or any(not isinstance(r,str) for r in value['allowed_regions']) or not set(value['allowed_regions'])<={'US','EU','APAC','OTHER'}:
            raise HTTPException(422,'Explicit approved regions required')
    elif kind=='wall_policy':
        if set(value)!={'deny_account_ids'} or not isinstance(value['deny_account_ids'],list) or any(not isinstance(v,str) for v in value['deny_account_ids']):
            raise HTTPException(422,'Wall policies support explicit additional denies only')
    else:
        if set(value)!={'languages','governing_laws','rules','test_cases','authorities','disclaimer'}:raise HTTPException(422,'Structured playbook fields required')
        if any(not isinstance(value[k],list) or not value[k] or any(not isinstance(v,str) for v in value[k]) for k in ['languages','governing_laws']):raise HTTPException(422,'Language and governing-law dimensions must be separate lists')
        if not isinstance(value['authorities'],list) or not isinstance(value['disclaimer'],str):raise HTTPException(422,'Authority references and draft disclaimer required')
        if not isinstance(value['rules'],list) or not 1<=len(value['rules'])<=50:raise HTTPException(422,'One to fifty rules required')
        ids=set()
        for rule in value['rules']:
            if not isinstance(rule,dict) or set(rule)!={'id','description','triggers'} or not isinstance(rule['id'],str) or rule['id'] in ids:raise HTTPException(422,'Stable unique rule IDs required')
            ids.add(rule['id'])
            if not isinstance(rule['triggers'],list) or not rule['triggers'] or any(not isinstance(t,str) or not 1<=len(t)<=200 for t in rule['triggers']):raise HTTPException(422,'Literal triggers required')
        if not isinstance(value['test_cases'],list) or not 2<=len(value['test_cases'])<=50:raise HTTPException(422,'Positive and negative synthetic cases required')
        for case in value['test_cases']:
            if not isinstance(case,dict) or set(case)!={'text','expected_rule_ids'} or not isinstance(case['text'],str) or len(case['text'])>10000 or not isinstance(case['expected_rule_ids'],list):raise HTTPException(422,'Invalid synthetic case')
            if any(not isinstance(v,str) or v not in ids for v in case['expected_rule_ids']):raise HTTPException(422,'Expected rule IDs must exist in this definition')
        if not any(c['expected_rule_ids'] for c in value['test_cases']) or not any(not c['expected_rule_ids'] for c in value['test_cases']):raise HTTPException(422,'Positive and negative cases required')


def test_playbook(db,actor,row):
    from kestrel.services.lifecycle import mutable
    mutable(db,row.matter_id)
    if row.kind!='legal_playbook' or row.state not in {'draft','submitted'}:raise HTTPException(409,'Draft or submitted legal playbook required')
    value=json.loads(row.definition_json)
    result=analyze_examples(value)
    passed=result['passed']
    if passed:row.tested_hash=row.content_hash
    audit(db,'playbook.test','passed' if passed else 'failed',actor.id,category='legal_sme',matter_id=row.matter_id,object_id=row.id)
    db.commit();return {**result,'content_hash':row.content_hash,'mode':'synthetic_literal_baseline'}


def analyze_examples(value):
    results=[]
    for case in value['test_cases']:
        hits=[]
        for rule in value['rules']:
            for trigger in rule['triggers']:
                match=re.search(re.escape(trigger),case['text'],flags=re.IGNORECASE)
                if match:
                    hits.append({'rule_id':rule['id'],'start':match.start(),'end':match.end(),'quote':case['text'][match.start():match.end()]});break
        results.append({'passed':{h['rule_id'] for h in hits}==set(case['expected_rule_ids']),'evidence':hits})
    passed=all(r['passed'] for r in results)
    return {'passed':passed,'cases':results}
