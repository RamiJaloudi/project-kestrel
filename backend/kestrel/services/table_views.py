"""Immutable private table configurations and independently reviewed named sharing.

Every configuration use rechecks its owner/recipient ACL and its evidence using the
canonical document PDP. Configuration text is never automatically classified.
"""
import json
from fastapi import HTTPException
from sqlalchemy import select
from kestrel import models as m
from kestrel.domain import Organization as O,Role as R
from kestrel.repositories.identity import principal
from kestrel.schemas.data_tables import TableQuery
from kestrel.services import data_tables as tables,workflow as w,review_work as rw,financial as f,lifecycle
from kestrel.services.auth import clock,audit
from kestrel.adapters.extraction import canonical,digest


def scope(db,actor,matter,dataset):
    from kestrel.services.questions import access
    access(actor,matter,db)
    if actor.org==O.BANK:
        gate=f.gate_row(db,matter)
        if dataset!='financial' or not gate or not gate.enabled:raise HTTPException(403,'Private bank financial views require the current financial gate')
    elif actor.org!=O.FIRM:raise HTTPException(403,'Saved table views unavailable for this audience')


def locked(db,matter):
    db.scalar(select(m.Matter).where(m.Matter.id==matter).with_for_update())
    lifecycle.mutable(db,matter)


def account_actor(db,uid):
    account=db.get(m.Account,uid)
    if not account or not account.active:raise HTTPException(403,'Identity no longer eligible')
    return principal(db,account,clock())


def omit_contract_default(query):
    filters=query.get('source_filters')
    if isinstance(filters,dict) and filters.get('contracts_only') is False:filters.pop('contracts_only')
    return query


def configuration_fingerprint(payload):
    value=payload.model_dump();omit_contract_default(value['query'])
    return digest(canonical(value).encode())


def normalized(query,matter,dataset):
    if query.matter_id!=matter:raise HTTPException(422,'Saved view cannot change matter')
    if query.task_filters is not None or query.finding_filters is not None:raise HTTPException(422,'Task and finding saved views require separately governed evidence support')
    if getattr(query,'saved_view_id',None) is not None or getattr(query,'saved_view_version_hash',None) is not None:raise HTTPException(422,'Saved configurations cannot recursively reference another saved view')
    columns=tables.INVENTORY_COLUMNS if dataset=='inventory' else tables.FINANCIAL_COLUMNS
    if (query.sort is not None and query.sort not in columns) or set(query.column_filters)-set(columns):raise HTTPException(422,'Unknown table sort or column filter')
    if dataset=='inventory' and query.financial_filters is not None:raise HTTPException(422,'Financial filters cannot apply to inventory')
    if dataset=='financial' and query.source_filters is not None:raise HTTPException(422,'Source filters cannot apply to financial facts')
    # draw/start are transport state, and cannot pin a disclosure or previous page.
    result=query.model_dump(mode='json');result.update(draw=0,start=0)
    # A query reference must not recursively embed another saved view.
    result.pop('saved_view_id',None)
    result.pop('saved_view_version_hash',None)
    result.pop('task_filters',None)
    result.pop('finding_filters',None)
    return omit_contract_default(result)


def reference(db,actor,kind,rid,matter):
    if kind=='source':
        src,policy=rw.source(db,actor,rid)
        if not policy.classification_confirmed:raise HTTPException(409,'Confirm evidence classification before binding saved content')
        retained=rw.capture(src,policy)
    else:
        fact=db.get(m.FinancialFact,rid)
        if not fact:raise HTTPException(403,'Saved financial evidence unavailable')
        src,policy,_=f.read(db,actor,fact)
        if {d.operation for d in f.history(db,fact)}&{'reject','revoke'}:raise HTTPException(403,'Saved financial evidence no longer active')
        retained={k:getattr(fact,k) for k in ['matter_id','source_id','retained_classification','retained_scope']}
    if src.matter_id!=matter or policy.matter_id!=matter:raise HTTPException(403,'Evidence outside saved view matter')
    return retained,policy


def evidence(db,version):
    return list(db.scalars(select(m.TableViewEvidence).where(m.TableViewEvidence.version_id==version.id).order_by(m.TableViewEvidence.kind,m.TableViewEvidence.reference_id)))


def bound(db,actor,version):
    refs=evidence(db,version)
    if version.handling=='source_bound' and not refs:raise HTTPException(403,'Saved content provenance missing')
    for ref in refs:
        retained,policy=reference(db,actor,ref.kind,ref.reference_id,version.matter_id)
        if retained['source_id']!=ref.source_id or w.snapshot(db,policy)!=ref.reference_snapshot:raise HTTPException(403,'Saved evidence attributes changed; create a new version')
        # Derivative-backed bank facts use their own release PDP. They never grant
        # access to original source IDs or to retained internal classifications.
        if actor.org==O.FIRM:rw.retained(db,actor,ref)
    return refs


def version_material(view,version,refs):
    return {'view_id':view.id,'matter_id':view.matter_id,'dataset':view.dataset,'owner_id':view.owner_id,'organization':view.organization,
        **{k:getattr(version,k) for k in ['revision','previous_hash','name','query_json','handling','rationale','created_by','created_at']},
        'evidence':[{'kind':r.kind,'id':r.reference_id,'snapshot':r.reference_snapshot,'source_id':r.source_id,
            'retained_classification':r.retained_classification,'retained_scope':r.retained_scope} for r in refs]}


def integrity(db,view,version):
    if not version or version.view_id!=view.id or version.matter_id!=view.matter_id:raise HTTPException(403,'Saved version unavailable')
    refs=evidence(db,version)
    if digest(canonical(version_material(view,version,refs)).encode())!=version.content_hash:raise HTTPException(403,'Saved configuration integrity denied')
    query=TableQuery.model_validate_json(version.query_json)
    if normalized(query,view.matter_id,view.dataset)!=json.loads(version.query_json):raise HTTPException(403,'Saved configuration contract denied')
    return query


def latest(db,view):
    return db.scalar(select(m.TableViewVersion).where(m.TableViewVersion.view_id==view.id).order_by(m.TableViewVersion.revision.desc()).limit(1))


def shares(db,vid):
    rows=list(db.scalars(select(m.TableViewShare).where(m.TableViewShare.version_id==vid).order_by(m.TableViewShare.created_at,m.TableViewShare.id).limit(101)))
    if len(rows)>100:raise HTTPException(413,'Saved configuration exceeds the local 100-share review limit')
    return rows


def decisions(db,share):
    return list(db.scalars(select(m.TableViewShareDecision).where(m.TableViewShareDecision.share_id==share.id).order_by(m.TableViewShareDecision.occurred_at,m.TableViewShareDecision.id)))


def recipients(db,share):
    return sorted(db.scalars(select(m.TableViewShareRecipient.account_id).where(m.TableViewShareRecipient.share_id==share.id)))


def share_material(share,ids):
    return {**{k:getattr(share,k) for k in ['version_id','matter_id','version_hash','requested_by','expires_at','rationale','created_at']},'recipient_ids':ids}


def share_integrity(db,share,version):
    ids=recipients(db,share)
    if share.version_id!=version.id or share.version_hash!=version.content_hash or not ids or digest(canonical(share_material(share,ids)).encode())!=share.content_hash:raise HTTPException(403,'Saved share integrity denied')
    return ids


def eligible(db,actor,view,version=None):
    scope(db,actor,view.matter_id,view.dataset)
    if actor.org!=O.FIRM or view.organization!=O.FIRM.value:raise HTTPException(403,'Sharing is restricted to internal firm identities')
    if version:integrity(db,view,version);bound(db,actor,version)


def active_share(db,view,version,share,actor):
    ids=share_integrity(db,share,version)
    if actor.id not in ids or clock()>=share.expires_at:return False
    rows=decisions(db,share);ops={d.operation:d for d in rows}
    if 'approve' not in ops or {'reject','revoke'}&set(ops):return False
    decision=ops['approve']
    if decision.content_hash!=share.content_hash or not decision.content_reviewed or decision.actor_id in {view.owner_id,share.requested_by,*ids}:return False
    reviewer=account_actor(db,decision.actor_id)
    if R.SME not in reviewer.roles:return False
    eligible(db,reviewer,view,version)
    owner=account_actor(db,view.owner_id);eligible(db,owner,view,version)
    eligible(db,actor,view,version)
    return True


def authorized_version(db,actor,view):
    scope(db,actor,view.matter_id,view.dataset)
    if view.organization!=actor.org.value:raise HTTPException(403,'Saved configuration unavailable')
    if actor.id==view.owner_id:
        version=latest(db,view);integrity(db,view,version);bound(db,actor,version);return version
    if actor.org!=O.FIRM:raise HTTPException(403,'Own private configuration required')
    for version in db.scalars(select(m.TableViewVersion).where(m.TableViewVersion.view_id==view.id).order_by(m.TableViewVersion.revision.desc())):
        integrity(db,view,version)
        for share in shares(db,version.id):
            if active_share(db,view,version,share,actor):return version
    raise HTTPException(403,'Own configuration or current independently approved named share required')


def row(db,vid):
    value=db.get(m.TableView,vid)
    if not value:raise HTTPException(404,'Saved configuration unavailable')
    return value


def share_state(db,share):
    ops={d.operation for d in decisions(db,share)}
    return 'revoked' if 'revoke' in ops else 'rejected' if 'reject' in ops else 'expired' if clock()>=share.expires_at else 'approved' if 'approve' in ops else 'pending'


def request_output(db,actor,view,version,share):
    ids=share_integrity(db,share,version)
    eligible(db,actor,view,version)
    state=share_state(db,share)
    can_review=R.SME in actor.roles and actor.id not in {view.owner_id,share.requested_by,*ids} and state=='pending'
    if actor.id!=view.owner_id and not can_review:raise HTTPException(403,'Independent review or owner access required')
    return {'id':share.id,'view_id':view.id,'version_id':version.id,'version_hash':version.content_hash,'content_hash':share.content_hash,
        'recipient_ids':ids,'expires_at':share.expires_at,'state':state,'rationale':share.rationale,
        'requested_by':share.requested_by,'can_review':can_review,'is_owner':actor.id==view.owner_id,
        'configuration':configuration_output(db,actor,view,version,include_requests=False),
        'decisions':[{'operation':d.operation,'actor_id':d.actor_id,'rationale':d.rationale,'content_reviewed':d.content_reviewed} for d in decisions(db,share)]}


def configuration_output(db,actor,view,version,include_requests=True):
    query=integrity(db,view,version);refs=bound(db,actor,version)
    value={'id':view.id,'matter_id':view.matter_id,'dataset':view.dataset,'owner_id':view.owner_id,'is_owner':actor.id==view.owner_id,
        'version_id':version.id,'revision':version.revision,'version_hash':version.content_hash,'name':version.name,'query':query.model_dump(mode='json'),
        'handling':version.handling,'evidence_refs':[{'kind':r.kind,'id':r.reference_id} for r in refs],
        'shared':actor.id!=view.owner_id,'can_review':False,'created_at':version.created_at,'share_requests':[]}
    if include_requests and actor.id==view.owner_id and actor.org==O.FIRM:
        value['share_requests']=[request_output(db,actor,view,version,s) for s in shares(db,version.id)]
    return value


def record_audit(db,actor,view,version,action,object_id):
    refs=evidence(db,version)
    if actor.org==O.FIRM and refs:
        for ref in refs:
            _,policy=reference(db,actor,ref.kind,ref.reference_id,view.matter_id)
            # The object resolves to all evidence refs in audit_records().
            rw.audit_work(db,actor,policy,action,type('AuditReference',(),{'id':object_id,'retained_classification':ref.retained_classification,'retained_scope':ref.retained_scope})())
    else:audit(db,action,'allowed',actor.id,category='access',matter_id=view.matter_id,object_id=object_id)


def add_version(db,actor,view,p,revision,previous_hash):
    query=normalized(p.query,view.matter_id,view.dataset)
    if actor.org==O.BANK and (p.handling!='source_bound' or not p.evidence_refs):raise HTTPException(422,'Private bank views require explicit released financial evidence references')
    refs=[]
    for ref in sorted(p.evidence_refs,key=lambda r:(r.kind,r.id)):
        if view.dataset=='financial' and ref.kind!='financial':raise HTTPException(422,'Financial views bind financial evidence references')
        if view.dataset=='inventory' and ref.kind!='source':raise HTTPException(422,'Inventory views bind source evidence references')
        retained,policy=reference(db,actor,ref.kind,ref.id,view.matter_id)
        refs.append(m.TableViewEvidence(**retained,kind=ref.kind,reference_id=ref.id,reference_snapshot=w.snapshot(db,policy)))
    version=m.TableViewVersion(view_id=view.id,matter_id=view.matter_id,revision=revision,previous_hash=previous_hash,name=p.name,query_json=canonical(query),handling=p.handling,
        rationale=p.rationale,created_by=actor.id,created_at=clock(),request_key=p.request_key,input_hash=configuration_fingerprint(p),content_hash='')
    version.content_hash=digest(canonical(version_material(view,version,refs)).encode())
    db.add(version);db.flush()
    for ref in refs:ref.version_id=version.id;db.add(ref)
    db.flush();record_audit(db,actor,view,version,'table_view.version.create',version.id)
    return version


def create(db,actor,p):
    scope(db,actor,p.matter_id,p.dataset);locked(db,p.matter_id)
    old=db.scalar(select(m.TableViewVersion).where(m.TableViewVersion.created_by==actor.id,m.TableViewVersion.request_key==p.request_key))
    if old:
        if old.input_hash!=configuration_fingerprint(p):raise HTTPException(409,'Request key changed')
        view=row(db,old.view_id);authorized_version(db,actor,view);return configuration_output(db,actor,view,old)
    view=m.TableView(matter_id=p.matter_id,dataset=p.dataset,owner_id=actor.id,organization=actor.org.value,created_at=clock());db.add(view);db.flush()
    version=add_version(db,actor,view,p,1,None);value=configuration_output(db,actor,view,version);db.commit();return value


def update(db,actor,vid,p):
    view=row(db,vid);scope(db,actor,view.matter_id,view.dataset)
    if view.owner_id!=actor.id or view.organization!=actor.org.value:raise HTTPException(403,'Own saved configuration required')
    locked(db,view.matter_id)
    old=db.scalar(select(m.TableViewVersion).where(m.TableViewVersion.created_by==actor.id,m.TableViewVersion.request_key==p.request_key))
    if old:
        if old.view_id!=view.id or old.input_hash!=configuration_fingerprint(p):raise HTTPException(409,'Request key changed')
        return configuration_output(db,actor,view,old)
    prior=latest(db,view);integrity(db,view,prior)
    # Rebinding new evidence after a policy change is allowed only to the owner;
    # the old version and every approval remain immutable and independently stale.
    if prior.content_hash!=p.expected_version_hash:raise HTTPException(409,'Saved configuration changed; refresh before updating')
    if prior.revision>=100:raise HTTPException(413,'Saved configuration exceeds the local 100-version limit; create a new private configuration')
    version=add_version(db,actor,view,p,prior.revision+1,prior.content_hash);value=configuration_output(db,actor,view,version);db.commit();return value


def get(db,actor,vid):
    view=row(db,vid);version=authorized_version(db,actor,view);value=configuration_output(db,actor,view,version)
    record_audit(db,actor,view,version,'table_view.read',version.id);db.commit();return value


def listing(db,actor,matter,dataset):
    scope(db,actor,matter,dataset);result=[]
    for view in db.scalars(select(m.TableView).where(m.TableView.matter_id==matter,m.TableView.dataset==dataset).order_by(m.TableView.created_at.desc(),m.TableView.id).limit(501)):
        try:
            version=authorized_version(db,actor,view);result.append(configuration_output(db,actor,view,version))
        except HTTPException as error:
            if error.status_code not in {403,404}:raise
    if len(result)>100:raise HTTPException(413,'Saved configuration list exceeds 100 permitted views')
    return result


def request_share(db,actor,vid,p):
    view=row(db,vid);version=authorized_version(db,actor,view);eligible(db,actor,view,version);locked(db,view.matter_id)
    if actor.id!=view.owner_id:raise HTTPException(403,'Only owner may request sharing')
    if version.handling!='source_bound' or p.version_hash!=version.content_hash:raise HTTPException(409,'Exact source-bound configuration required; ambiguous private text needs an evidence-bound version and independent content review')
    old=db.scalar(select(m.TableViewShare).where(m.TableViewShare.requested_by==actor.id,m.TableViewShare.request_key==p.request_key))
    if old:
        if old.version_id!=version.id or old.input_hash!=rw.fingerprint(p):raise HTTPException(409,'Share request key changed')
        return request_output(db,actor,view,version,old)
    if len(shares(db,version.id))>=100:raise HTTPException(413,'Saved configuration exceeds the local 100-share review limit')
    for uid in p.recipient_ids:
        if uid==view.owner_id:raise HTTPException(422,'Choose a named recipient other than owner')
        eligible(db,account_actor(db,uid),view,version)
    now=clock();share=m.TableViewShare(version_id=version.id,matter_id=view.matter_id,version_hash=version.content_hash,requested_by=actor.id,expires_at=now+p.expires_in_days*86400,
        rationale=p.rationale,created_at=now,request_key=p.request_key,input_hash=rw.fingerprint(p),content_hash='')
    share.content_hash=digest(canonical(share_material(share,sorted(p.recipient_ids))).encode());db.add(share);db.flush()
    for uid in sorted(p.recipient_ids):db.add(m.TableViewShareRecipient(share_id=share.id,matter_id=view.matter_id,account_id=uid))
    db.flush();record_audit(db,actor,view,version,'table_view.share.request',share.id);value=request_output(db,actor,view,version,share);db.commit();return value


def decide(db,actor,sid,p):
    share=db.get(m.TableViewShare,sid)
    if not share:raise HTTPException(404,'Share request unavailable')
    version=db.get(m.TableViewVersion,share.version_id);view=row(db,version.view_id)
    scope(db,actor,view.matter_id,view.dataset)
    if actor.org!=O.FIRM:raise HTTPException(403,'Internal share decisions only')
    db.scalar(select(m.Matter).where(m.Matter.id==view.matter_id).with_for_update())
    ids=share_integrity(db,share,version);integrity(db,view,version)
    if p.content_hash!=share.content_hash:raise HTTPException(409,'Exact share request hash required')
    ops={d.operation for d in decisions(db,share)}
    if 'revoke' in ops or p.operation in ops or (p.operation in {'approve','reject'} and ops&{'approve','reject'}):raise HTTPException(409,'Decision already recorded; retained history is immutable')
    if p.operation=='revoke':
        # Access tightening must remain available after freeze, source drift or
        # recipient/approver revocation. No config is returned through this path.
        if actor.id!=view.owner_id and R.SME not in actor.roles:raise HTTPException(403,'Owner or scoped SME revocation required')
    else:
        lifecycle.mutable(db,view.matter_id);eligible(db,actor,view,version)
        if R.SME not in actor.roles or actor.id in {view.owner_id,share.requested_by,*ids}:raise HTTPException(403,'Independent source-cleared nonrecipient SME required')
        if clock()>=share.expires_at:raise HTTPException(409,'Share request expired')
        eligible(db,account_actor(db,view.owner_id),view,version)
        for uid in ids:eligible(db,account_actor(db,uid),view,version)
        if p.operation=='approve' and not p.content_reviewed:raise HTTPException(422,'Explicit review of all saved names, query/filter text, provenance and sharing rationale required')
    decision=m.TableViewShareDecision(share_id=share.id,matter_id=view.matter_id,operation=p.operation,content_hash=share.content_hash,
        content_reviewed=p.content_reviewed,actor_id=actor.id,rationale=p.rationale,occurred_at=clock());db.add(decision);db.flush()
    if p.operation=='revoke':
        # Retained audit resolver supplies all original restriction captures.
        audit(db,'table_view.share.revoke','allowed',actor.id,category='access',matter_id=view.matter_id,object_id=decision.id)
    else:record_audit(db,actor,view,version,'table_view.share.'+p.operation,decision.id)
    db.commit();return {'id':share.id,'content_hash':share.content_hash,'state':share_state(db,share)}


def review_queue(db,actor,matter,dataset):
    scope(db,actor,matter,dataset)
    if actor.org!=O.FIRM:raise HTTPException(403,'Internal owner history or independent legal SME review required')
    result=[]
    for share in db.scalars(select(m.TableViewShare).where(m.TableViewShare.matter_id==matter).order_by(m.TableViewShare.created_at.desc()).limit(501)):
        version=db.get(m.TableViewVersion,share.version_id);view=row(db,version.view_id)
        if view.dataset!=dataset:continue
        try:result.append(request_output(db,actor,view,version,share))
        except HTTPException as error:
            if error.status_code not in {403,404}:raise
    if len(result)>100:raise HTTPException(413,'Share review queue exceeds 100 permitted requests')
    return result


def eligible_people(db,actor,matter,dataset):
    scope(db,actor,matter,dataset)
    if actor.org!=O.FIRM:raise HTTPException(403,'Internal named sharing only')
    result=[]
    for account in db.scalars(select(m.Account).where(m.Account.active==True).order_by(m.Account.id).limit(501)):
        if account.id==actor.id:continue
        other=principal(db,account,clock())
        try:
            scope(db,other,matter,dataset)
            if other.org!=O.FIRM:continue
            result.append({'id':account.id,'name':account.display_name or account.username})
        except HTTPException as error:
            if error.status_code!=403:raise
    return result


def resolve_selection(db,actor,vid,expected_matter,dataset):
    view=row(db,vid)
    if view.matter_id!=expected_matter or view.dataset!=dataset:raise HTTPException(403,'Saved configuration scope mismatch')
    version=authorized_version(db,actor,view)
    return integrity(db,view,version),version.content_hash


def resolve_query(db,actor,vid,expected_matter,dataset):
    return resolve_selection(db,actor,vid,expected_matter,dataset)[0]


def audit_records(db,object_id):
    """Return original retained evidence captures for protected audit resolution."""
    direct=db.get(m.TableViewEvidence,object_id)
    if direct:return [direct]
    view=db.get(m.TableView,object_id)
    if view:
        return list(db.scalars(select(m.TableViewEvidence).join(m.TableViewVersion,m.TableViewEvidence.version_id==m.TableViewVersion.id).where(m.TableViewVersion.view_id==view.id)))
    version=db.get(m.TableViewVersion,object_id)
    if not version:
        share=db.get(m.TableViewShare,object_id)
        if not share:
            recipient=db.get(m.TableViewShareRecipient,object_id)
            if recipient:share=db.get(m.TableViewShare,recipient.share_id)
        if not share:
            decision=db.get(m.TableViewShareDecision,object_id)
            share=db.get(m.TableViewShare,decision.share_id) if decision else None
        if share:version=db.get(m.TableViewVersion,share.version_id)
    return evidence(db,version) if version else []
