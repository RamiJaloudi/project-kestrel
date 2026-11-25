"""Global firm-Root directory. This service never grants legal/source access."""
import json,time,threading
from collections import defaultdict,deque
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from kestrel import models as m
from kestrel.domain import Organization as O,Role as R
from kestrel.schemas.account_directory import AccountFilters,AccountMetadata
from kestrel.services import auth

COLUMNS={'id','upn','display_name','employee_id','organization','roles','active','revision'}
_lock=threading.Lock();_requests={}


def require_root(actor):
    if actor.org!=O.FIRM or R.ROOT_ADMIN not in actor.roles:raise HTTPException(403,'Administrator required')


def fresh(db,request,actor_id):
    db.expire_all();identity=auth.authenticate(db,request)
    if identity[2].id!=actor_id:raise HTTPException(403,'Identity changed during directory request')
    require_root(identity[2]);return identity


def throttle(actor_id):
    now=time.monotonic()
    with _lock:
        for uid in list(_requests):
            if not _requests[uid] or _requests[uid][-1]<now-60:del _requests[uid]
        queue=_requests.setdefault(actor_id,deque())
        while queue and queue[0]<now-60:queue.popleft()
        if len(queue)>=60:raise HTTPException(429,'Account directory request limit reached; wait before retrying')
        queue.append(now)


def metadata(db,account):
    roles=db.scalars(select(m.Role.name).join(m.RoleGrant,m.RoleGrant.role_id==m.Role.id).where(m.RoleGrant.account_id==account.id)).all()
    return AccountMetadata(id=account.id,upn=account.username,display_name=account.display_name,employee_id=account.employee_id,
        organization=db.get(m.Organization,account.organization_id).code,roles=sorted(roles),active=account.active,revision=account.profile_revision)


def rows(db,filters=None,*,account_id=None,projection=None):
    filters=filters or AccountFilters()
    conditions=[]
    if filters.organization is not None:conditions.append(m.Organization.code==filters.organization)
    if filters.active is not None:conditions.append(m.Account.active==filters.active)
    if account_id is not None:conditions.append(m.Account.id==account_id)
    if projection is not None:
        statement=select(m.Account).join(m.Organization,m.Organization.id==m.Account.organization_id).where(*conditions).order_by(m.Account.username,m.Account.id)
        return [projection(db,account).model_dump() for account in db.scalars(statement)]
    statement=select(m.Account.id,m.Account.username,m.Account.display_name,m.Account.employee_id,m.Organization.code,m.Account.active,m.Account.profile_revision).join(
        m.Organization,m.Organization.id==m.Account.organization_id).where(*conditions).order_by(m.Account.username,m.Account.id)
    selected=list(db.execute(statement));names=defaultdict(list)
    if selected:
        for uid,name in db.execute(select(m.RoleGrant.account_id,m.Role.name).join(m.Role,m.Role.id==m.RoleGrant.role_id).where(m.RoleGrant.account_id.in_([row[0] for row in selected]))):names[uid].append(name)
    return [AccountMetadata(id=row[0],upn=row[1],display_name=row[2],employee_id=row[3],organization=row[4],roles=sorted(names[row[0]]),active=row[5],revision=row[6]).model_dump() for row in selected]


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)


def denied(db,actor_id,operation,error):
    db.rollback()
    if error.status_code in {401,403,409}:
        auth.audit(db,'account.directory.'+operation+'.denied','denied',actor_id);db.commit()


def guarded_read(db,actor,request,operation,prepare,object_id=None):
    actor_id=actor[2].id
    try:
        fresh(db,request,actor_id);throttle(actor_id);result=prepare()
        fresh(db,request,actor_id);current=prepare()
        fresh(db,request,actor_id)
        if canonical(result)!=canonical(current):raise HTTPException(409,'Account directory metadata changed; refresh before retrying')
        auth.audit(db,'account.directory.'+operation,'allowed',actor_id,object_id=object_id);db.commit();return result
    except HTTPException as error:
        denied(db,actor_id,operation,error);raise


def text(value):
    if isinstance(value,list):return ' '.join(value).casefold()
    return str(value).casefold()


def query(db,actor,p,request):
    def prepare():
        baseline=rows(db,p.account_filters);needle=p.search.casefold()
        def matches(row):
            return (not needle or any(needle in text(row[key]) for key in COLUMNS)) and all(not value or (row[key]==value if key=='id' else value.casefold() in text(row[key])) for key,value in p.column_filters.items())
        filtered=[row for row in baseline if matches(row)]
        filtered.sort(key=lambda row:((row[p.sort] if p.sort in {'active','revision'} else text(row[p.sort])),row['id']),reverse=p.direction=='desc')
        return {'draw':p.draw,'recordsTotal':len(baseline),'recordsFiltered':len(filtered),'data':filtered[p.start:p.start+p.length],
            'count_basis':'Current firm Root account directory; organization and active filters define the baseline, then literal global and column search determine filtered count.'}
    return guarded_read(db,actor,request,'query',prepare)


def listing(db,actor,request,projection=None):
    return guarded_read(db,actor,request,'list',lambda:rows(db,projection=projection))


def detail(db,actor,account_id,revision,request):
    def prepare():
        selected=rows(db,account_id=account_id)
        if not selected:raise HTTPException(404,'Account not found')
        if selected[0]['revision']!=revision:raise HTTPException(409,'Account profile revision changed; reload before editing')
        return selected[0]
    return guarded_read(db,actor,request,'detail',prepare,account_id)


def prepare_edit(db,account,payload):
    # No persistent mutation occurs before the second authority check.
    result=metadata(db,account).model_dump()
    result.update(display_name=payload.display_name,employee_id=payload.employee_id,revision=account.profile_revision+1)
    return result


def edit(db,actor,account_id,payload,request):
    actor_id=actor[2].id
    try:
        fresh(db,request,actor_id)
        account=db.scalar(select(m.Account).where(m.Account.id==account_id).with_for_update().execution_options(populate_existing=True))
        if account is None:raise HTTPException(404,'Account not found')
        if account.profile_revision!=payload.expected_revision:raise HTTPException(409,'Account changed; refresh before editing')
        prepared=prepare_edit(db,account,payload)
        fresh(db,request,actor_id)
        if account.profile_revision!=payload.expected_revision:raise HTTPException(409,'Account changed; refresh before editing')
        account.display_name=payload.display_name;account.employee_id=payload.employee_id;account.profile_revision+=1
        db.flush();result=metadata(db,account).model_dump()
        fresh(db,request,actor_id);current=metadata(db,db.get(m.Account,account_id)).model_dump()
        fresh(db,request,actor_id)
        if canonical(result)!=canonical(current) or any(current[key]!=prepared[key] for key in ['id','display_name','employee_id','revision']):raise HTTPException(409,'Account changed before metadata receipt')
        auth.audit(db,'account.metadata','allowed',actor_id,object_id=account_id);db.commit();return current
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Employee ID already belongs to this employer') from None
    except HTTPException as error:
        denied(db,actor_id,'edit',error);raise
