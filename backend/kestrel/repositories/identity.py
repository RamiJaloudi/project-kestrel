from sqlalchemy import select
import json
from kestrel.models import Account, Organization, Role, RoleGrant, MatterAssignment, EthicalWall, CleanTeamMembership, MatterValidation
from kestrel.domain import Principal, Organization as Org, Role as DomainRole
from kestrel.models import GovernanceVersion


def principal(db, account: Account, now: int) -> Principal:
    org = db.get(Organization, account.organization_id)
    roles = db.scalars(select(Role.name).join(RoleGrant, Role.id == RoleGrant.role_id).where(RoleGrant.account_id == account.id)).all()
    matters = db.scalars(select(MatterAssignment.matter_id).join(MatterValidation, MatterValidation.matter_id == MatterAssignment.matter_id).where(
        MatterValidation.status == "validated",
        MatterAssignment.account_id == account.id, MatterAssignment.starts_at <= now,
        MatterAssignment.expires_at > now, MatterAssignment.revoked.is_(False))).all()
    walls = db.scalars(select(EthicalWall.matter_id).where(EthicalWall.account_id == account.id, EthicalWall.active.is_(True))).all()
    for policy in db.scalars(select(GovernanceVersion).where(GovernanceVersion.kind=='wall_policy',GovernanceVersion.state=='published')):
        if account.id in json.loads(policy.definition_json)['deny_account_ids']:walls.append(policy.matter_id)
    from kestrel.repositories.walls import state as wall_state
    scoped=wall_state(db,account.id,set(roles),now)
    walls.extend(scoped['denied_matters'])
    # Retain matter+scope pairs in policy queries; never flatten scope across matters.
    return Principal(account.id, Org(org.code), frozenset(DomainRole(r) for r in roles), frozenset(matters), frozenset(walls),client_walls=frozenset(scoped['client']))


def clean_scope(db, account_id: str, matter: str, scope: str, now: int) -> bool:
    return db.scalar(select(CleanTeamMembership.id).where(
        CleanTeamMembership.account_id == account_id, CleanTeamMembership.matter_id == matter,
        CleanTeamMembership.scope == scope, CleanTeamMembership.starts_at <= now,
        CleanTeamMembership.expires_at > now, CleanTeamMembership.revoked.is_(False))) is not None
