from fastapi import APIRouter, Depends, HTTPException, Request
from kestrel.api.auth import identity, database
from kestrel.schemas.agent_registry import Create, Version, Action, ImpactDecision, Notification
from kestrel.services import agent_registry as service
from kestrel.services.auth import authenticate, audit
from kestrel.services.data_tables import throttle, authorization_inputs

router = APIRouter(prefix='/api/v1/agent-registry', tags=['Versioned agent registry and SME rerun impacts'])


def execute(db, actor, request, matter, operation, call, validate=None):
    try:
        throttle(actor)
        before = authorization_inputs(db, matter, actor.id)
        value = call(actor)
        db.expire_all()
        current = authenticate(db, request)[2]
        service.access(current, matter, {service.R.ROOT_ADMIN, service.R.SME})
        if authorization_inputs(db, matter, current.id) != before:
            raise HTTPException(409, 'Authorization scope changed while preparing agent governance response')
        if validate: validate(current, value)
        return value
    except HTTPException as error:
        if error.status_code in {401, 403, 409}:
            db.rollback(); audit(db, 'agent_profile.' + operation + '.denied', 'denied', actor.id, category='access'); db.commit()
        raise


@router.get('/catalog')
def catalog(actor=Depends(identity)):
    if actor[2].org != service.O.FIRM or not actor[2].roles.intersection({service.R.ROOT_ADMIN, service.R.SME}):
        raise HTTPException(403, 'Internal agent governance role required')
    return service.catalog()


@router.get('')
def listing(matter_id: str, request: Request, actor=Depends(identity), db=Depends(database)):
    return execute(db, actor[2], request, matter_id, 'list', lambda current: service.listing(db, current, matter_id),
        lambda current, rows: [service.output(db, current, db.get(service.m.AgentProfileVersion, row['id'])) for row in rows])


@router.post('', status_code=201)
def create(payload: Create, request: Request, actor=Depends(identity), db=Depends(database)):
    return execute(db, actor[2], request, payload.matter_id, 'create', lambda current: service.create(db, current, payload))


@router.post('/profiles/{profile_id}/versions', status_code=201)
def append(profile_id: str, payload: Version, request: Request, actor=Depends(identity), db=Depends(database)):
    profile = db.get(service.m.AgentProfile, profile_id)
    if profile is None: raise HTTPException(404, 'Agent profile unavailable')
    return execute(db, actor[2], request, profile.matter_id, 'version', lambda current: service.append(db, current, profile_id, payload))


@router.post('/versions/{version_id}/actions')
def action(version_id: str, payload: Action, request: Request, actor=Depends(identity), db=Depends(database)):
    version = db.get(service.m.AgentProfileVersion, version_id)
    if version is None: raise HTTPException(404, 'Agent version unavailable')
    return execute(db, actor[2], request, version.matter_id, payload.operation, lambda current: service.transition(db, current, version_id, payload))


@router.get('/diff')
def compare(from_id: str, to_id: str, request: Request, actor=Depends(identity), db=Depends(database)):
    before, after = db.get(service.m.AgentProfileVersion, from_id), db.get(service.m.AgentProfileVersion, to_id)
    if before is None or after is None: raise HTTPException(404, 'Agent version unavailable')
    def call(current):
        service.output(db, current, before); service.output(db, current, after)
        if before.profile_id != after.profile_id: raise HTTPException(403, 'Same-profile version comparison required')
        return {'from_id': before.id, 'to_id': after.id, 'changes': service.diff(service.checked(db, before).model_dump(mode='json'), service.checked(db, after).model_dump(mode='json'))}
    return execute(db, actor[2], request, before.matter_id, 'diff', call)


@router.get('/impacts')
def impacts(matter_id: str, request: Request, actor=Depends(identity), db=Depends(database)):
    return execute(db, actor[2], request, matter_id, 'impacts', lambda current: service.impacts(db, current, matter_id),
        lambda current, rows: [service.task_read(db, current, row['id']) for row in rows])


@router.post('/impacts/{task_id}/notification')
def notification(task_id: str, payload: Notification, request: Request, actor=Depends(identity), db=Depends(database)):
    task = db.get(service.m.AgentProfileImpactTask, task_id)
    if task is None: raise HTTPException(404, 'Agent impact unavailable')
    return execute(db, actor[2], request, task.matter_id, 'notification', lambda current: service.notify(db, current, task_id, payload),
        lambda current, value: service.task_read(db, current, value['id']))


@router.post('/impacts/{task_id}/decisions')
def decision(task_id: str, payload: ImpactDecision, request: Request, actor=Depends(identity), db=Depends(database)):
    task = db.get(service.m.AgentProfileImpactTask, task_id)
    if task is None: raise HTTPException(404, 'Agent impact unavailable')
    return execute(db, actor[2], request, task.matter_id, 'impact_decision', lambda current: service.decide_impact(db, current, task_id, payload),
        lambda current, value: service.task_read(db, current, value['id']))
