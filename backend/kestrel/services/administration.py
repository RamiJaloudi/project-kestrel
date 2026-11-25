"""Synthetic registry administration; real Intapp integration is not implied."""
from fastapi import HTTPException
from sqlalchemy import select, update, text, bindparam
from kestrel.models import (Client, Matter, MatterAssignment, MatterValidation, EthicalWall,
                            Account, AdministrationDecision,Organization as OrganizationRow)
from kestrel.domain import Role, Organization
from kestrel.services.auth import clock, audit
from kestrel.repositories.identity import principal
from sqlalchemy.exc import IntegrityError
from kestrel.services.registry_numbers import next_number


def require_admin(actor):
    if actor.org != Organization.FIRM or Role.ROOT_ADMIN not in actor.roles:
        raise HTTPException(403, "Administrator required")


def scopes(db, actor):
    require_admin(actor)
    now = clock()
    return set(db.scalars(select(MatterAssignment.matter_id).where(
        MatterAssignment.account_id == actor.id, MatterAssignment.revoked.is_(False),
        MatterAssignment.starts_at <= now, MatterAssignment.expires_at > now)).all()) - set(actor.walls)


def require_matter(db, actor, matter):
    if matter not in scopes(db, actor):
        raise HTTPException(403, "Matter administration denied")
    validation = db.get(MatterValidation, matter)
    if validation is None:
        raise HTTPException(403, "Matter administration denied")
    return validation


def advance(db, validation, expected):
    result = db.execute(update(MatterValidation).where(MatterValidation.matter_id == validation.matter_id,
                       MatterValidation.revision == expected).values(revision=expected+1))
    if result.rowcount != 1:
        raise HTTPException(409, "Registry changed; refresh before deciding")


def record(db, actor, matter, kind, rationale, revision, target=None):
    db.add(AdministrationDecision(matter_id=matter, actor_id=actor.id, target_id=target,
           kind=kind, rationale=rationale, revision=revision, occurred_at=clock()))
    audit(db, kind, "allowed", actor.id,matter_id=matter)


def client_rows(db, actor):
    allowed = scopes(db, actor)
    rows = db.execute(select(Client).outerjoin(MatterValidation, Client.id == MatterValidation.client_id).where(
        (Client.created_by == actor.id) | MatterValidation.matter_id.in_(allowed))).scalars().unique()
    return [{"id": c.id, "name": c.name,'client_number':c.client_number} for c in rows if c.id not in actor.client_walls]


def create_client(db,actor,name,number=None,*,commit=True):
    require_admin(actor)
    row=Client(name=name,created_by=actor.id,client_number=number or next_number(db,Client.client_number))
    db.add(row);audit(db,'client.created','allowed',actor.id)
    try:
        if commit:db.commit()
        else:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Client number already exists; refresh and retry')
    return {'id':row.id,'name':row.name,'client_number':row.client_number}


def registry(db, actor):
    allowed = scopes(db, actor)
    # SQL views are a read projection, never an authorization boundary.
    if not allowed:
        return []
    statement = text("SELECT * FROM vw_client_matter_validation WHERE matter_id IN :ids ORDER BY matter_name")
    rows = db.execute(statement.bindparams(bindparam("ids", expanding=True)), {"ids": sorted(allowed)}).mappings()
    return [dict(row) for row in rows]


def create_matter(db, actor, client_id, name, number=None,*,commit=True):
    if client_id not in {row['id'] for row in client_rows(db, actor)}:
        raise HTTPException(403, "Client administration denied")
    matter = Matter(name=name)
    db.add(matter); db.flush()
    number=number or next_number(db,MatterValidation.matter_number,MatterValidation.client_id==client_id)
    db.add(MatterValidation(matter_id=matter.id, client_id=client_id,matter_number=number))
    # Management scope for this new empty matter; no validation or content bypass.
    db.add(MatterAssignment(account_id=actor.id, matter_id=matter.id, expires_at=clock()+86400*30))
    record(db, actor, matter.id, "matter.created", "New synthetic registry matter", 1)
    try:
        if commit:db.commit()
        else:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Client/matter number pair already exists; refresh and retry')
    client=db.get(Client,client_id)
    return {"id": matter.id, "status": "pending", "revision": 1,'matter_number':number,'client_matter_number':client.client_number+'-'+number}


def decide(db, actor, matter, payload,*,commit=True):
    validation = require_matter(db, actor, matter)
    advance(db, validation, payload.expected_revision)
    validation.status = payload.status
    record(db, actor, matter, "matter."+payload.status, payload.rationale, payload.expected_revision+1)
    if commit:db.commit()
    else:db.flush()
    return {"revision": payload.expected_revision+1}


def access_rows(db, actor, matter,*,now=None):
    require_matter(db, actor, matter)
    now=clock() if now is None else now
    participants=select(MatterAssignment.account_id).where(MatterAssignment.matter_id==matter).union(select(EthicalWall.account_id).where(EthicalWall.matter_id==matter))
    assigned=set(db.scalars(select(MatterAssignment.account_id).where(MatterAssignment.matter_id==matter,
        MatterAssignment.starts_at<=now,MatterAssignment.expires_at>now,MatterAssignment.revoked.is_(False))))
    blocked=set(db.scalars(select(EthicalWall.account_id).where(EthicalWall.matter_id==matter,EthicalWall.active.is_(True))))
    return [{'matter_id':matter,'account_id':account.id,'username':account.username,'organization':organization,
        'assigned':int(account.id in assigned),'blocked':int(account.id in blocked),
        'effective_blocked':matter in principal(db,account,now).walls}
        for account,organization in db.execute(select(Account,OrganizationRow.code).join(OrganizationRow,Account.organization_id==OrganizationRow.id)
            .where(Account.id.in_(participants)).order_by(Account.username,Account.id))]


def set_access(db, actor, matter, payload,*,commit=True):
    validation = require_matter(db, actor, matter)
    target = db.scalar(select(Account).where(Account.username == payload.username.strip().casefold()))
    if target is None:
        raise HTTPException(404, "Target unavailable")
    if target.id == actor.id:
        raise HTTPException(403, "Self-access changes are prohibited")
    existing_wall=db.scalar(select(EthicalWall.id).where(EthicalWall.account_id==target.id,EthicalWall.matter_id==matter,EthicalWall.active.is_(True))) is not None
    if payload.blocked!=existing_wall:
        raise HTTPException(403,'Direct wall changes disabled; use independently approved Conflicts wall policies')
    advance(db, validation, payload.expected_revision)
    # Assignment commands preserve all historical/direct wall records exactly.
    db.execute(update(MatterAssignment).where(MatterAssignment.account_id == target.id,
               MatterAssignment.matter_id == matter).values(revoked=True))
    if payload.assigned:
        db.add(MatterAssignment(account_id=target.id, matter_id=matter, expires_at=clock()+payload.days*86400))
    record(db, actor, matter, f"access.assigned_{int(payload.assigned)}.wall_{int(payload.blocked)}",
           payload.rationale, payload.expected_revision+1, target.id)
    if commit:db.commit()
    else:db.flush()
    return {"revision": payload.expected_revision+1}
