"""Trusted local operator CLI; no remote signup or default passwords."""
import argparse
from getpass import getpass
from sqlalchemy import select
from kestrel.database import database_url, make_engine, factory
from kestrel.models import Account, Organization, Role, RoleGrant, ServerSession
from kestrel.domain import Role as DomainRole
from kestrel.services.auth import HASHER, audit


def provision(db, username, org_code, roles, password, email=None):
    username = username.strip().casefold()
    roles = set(roles)
    if not username or len(username) > 128 or not 15 <= len(password) <= 256:
        raise ValueError("Username and a 15–256 character password required")
    permitted = {"firm": {r.value for r in DomainRole} - {"client_user", "bank_analyst"},
                 "halden": {"client_user"}, "castlegate": {"bank_analyst"}}
    if org_code not in permitted or not roles or not roles <= permitted[org_code]:
        raise ValueError("Invalid organization role combination")
    if db.scalar(select(Account.id).where(Account.username == username)):
        raise ValueError("Account already exists; use reset/revoke commands")
    org = db.scalar(select(Organization).where(Organization.code == org_code))
    if org is None:
        org = Organization(code=org_code)
        db.add(org)
        db.flush()
    if email is not None:
        import re
        email = email.strip().casefold()
        if len(email)>254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError("Valid email required")
    account = Account(display_name=username.split("@")[0].replace("."," ").replace("_"," ").title(), username=username, email=email, organization_id=org.id, password_hash=HASHER.hash(password))
    db.add(account)
    db.flush()
    for name in roles:
        role = db.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(name=name)
            db.add(role)
            db.flush()
        db.add(RoleGrant(account_id=account.id, role_id=role.id))
    audit(db, "account.provision", "allowed", account.id)
    db.commit()
    return account


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "reset", "revoke"])
    parser.add_argument("username")
    parser.add_argument("--org", choices=["firm", "halden", "castlegate"])
    parser.add_argument("--roles", nargs="+", choices=[r.value for r in DomainRole])
    parser.add_argument("--email")
    args = parser.parse_args()
    with factory(make_engine(database_url()))() as db:
        if args.action == "create":
            password = getpass("New password (15+ characters): ")
            if password != getpass("Confirm password: "):
                parser.error("Passwords differ")
            account = provision(db, args.username, args.org, args.roles or [], password, args.email)
            print(f"Created account {account.id}; no matter access assigned")
        else:
            account = db.scalar(select(Account).where(Account.username == args.username.strip().casefold()))
            if account is None:
                parser.error("Account not found")
            if args.action == "reset":
                password = getpass("New password (15+ characters): ")
                if not 15 <= len(password) <= 256 or password != getpass("Confirm password: "):
                    parser.error("Password length/confirmation invalid")
                account.password_hash = HASHER.hash(password)
                account.password_customized = True
            for session in db.scalars(select(ServerSession).where(ServerSession.account_id == account.id)):
                session.revoked = True
            audit(db, "account." + args.action, "allowed", account.id)
            db.commit()
            print("Sessions revoked")


if __name__ == "__main__":
    main()
