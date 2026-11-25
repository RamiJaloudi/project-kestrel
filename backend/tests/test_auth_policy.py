import time
import os
import uuid
import pytest
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, delete
from kestrel.main import create_app
from kestrel.database import make_engine, factory
from kestrel.models import (Base, Account, ServerSession, Matter, MatterAssignment,
                            EthicalWall, CleanTeamMembership, RoleGrant, Client, MatterValidation)
from kestrel.bootstrap import provision
from kestrel.api.auth import database, identity
from kestrel.services import auth
import reference_policy as policy

PASSWORD = "synthetic-test-only-passphrase"


@pytest.fixture
def env(tmp_path, monkeypatch):
    pg_engine = None
    schema = None
    if os.environ.get('KESTREL_TEST_POSTGRES') == '1':
        from kestrel.database import database_url
        from sqlalchemy.engine import make_url
        from sqlalchemy.schema import CreateSchema
        pg_engine = make_engine(database_url())
        schema = 'kestrel_test_'+uuid.uuid4().hex
        with pg_engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        url = make_url(database_url()).update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    else:
        url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = make_engine(url)
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    monkeypatch.setenv("KESTREL_DATABASE_URL", url)
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    sessions = factory(engine)
    with sessions() as db:
        lawyer = provision(db, "lawyer", "firm", ["firm_lawyer"], PASSWORD)
        bank = provision(db, "bank", "castlegate", ["bank_analyst"], PASSWORD)
        root = provision(db, "root", "firm", ["root_admin"], PASSWORD)
        client = provision(db, "client", "halden", ["client_user"], PASSWORD)
        sme = provision(db, "sme", "firm", ["legal_sme"], PASSWORD)
        matter = Matter(name="Synthetic matter")
        other = Matter(name="Other synthetic matter")
        db.add_all([matter, other])
        db.flush()
        registry_client = Client(name="Synthetic client", created_by=root.id)
        db.add(registry_client); db.flush()
        for item in [matter, other]:
            db.add(MatterValidation(matter_id=item.id, client_id=registry_client.id, status="validated"))
        ids = {"lawyer": lawyer.id, "bank": bank.id, "root": root.id, "client": client.id, "sme": sme.id,
               "matter": matter.id, "other": other.id}
        for account in [lawyer, bank, root, client, sme]:
            db.add(MatterAssignment(account_id=account.id, matter_id=matter.id, expires_at=auth.clock()+3600))
        db.commit()
    app = create_app(engine)

    # Test-only route exercises the production identity dependency + legacy reference model;
    # no source endpoints or synthetic actor overrides shipped in the application.
    @app.get("/test/source/{matter_id}")
    def source(matter_id: str, label: str = "ordinary", scope: str | None = None,
               actor=Depends(identity), db=Depends(database)):
        if not policy.allowed(db, actor[2], action="read_source", matter=matter_id,
                              now=auth.clock(), label=label, scope=scope):
            raise HTTPException(403, "Access denied")
        return {"text": "synthetic source"}

    with TestClient(app, base_url="https://firm.localhost") as http:
        yield http, sessions, ids, app
    engine.dispose()
    if pg_engine is not None:
        from sqlalchemy.schema import DropSchema
        with pg_engine.begin() as connection:
            connection.execute(DropSchema(schema,cascade=True))
        pg_engine.dispose()


def login(http, name="lawyer", origin="https://firm.localhost", **extra):
    return http.post("/api/v1/auth/login", json={"username": name, "password": PASSWORD, **extra}, headers={"origin": origin})


def test_login_storage_cookie_logout(env):
    http, sessions, ids, _ = env
    result = login(http)
    assert result.status_code == 200
    cookie = result.headers["set-cookie"]
    assert all(x in cookie for x in ["Secure", "HttpOnly", "SameSite=strict", "Path=/"])
    assert "Domain=" not in cookie
    token = http.cookies.get(auth.COOKIE)
    with sessions() as db:
        account = db.get(Account, ids["lawyer"])
        assert account.password_hash.startswith("$argon2id$")
        session = db.scalar(select(ServerSession))
        assert session.token_hash == auth.digest(token) and session.token_hash != token
        assert session.csrf_hash == auth.digest(result.json()["csrf_token"])
    assert http.get("/api/v1/auth/me").json()["id"] == ids["lawyer"]
    assert http.post("/api/v1/auth/logout", headers={"origin": "https://firm.localhost", "x-csrf-token": result.json()["csrf_token"]}).status_code == 204
    assert http.get("/api/v1/auth/me").status_code == 401
    http.cookies.set(auth.COOKIE, token, domain="firm.localhost", path="/")
    assert http.get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize("change", ["expired", "revoked", "inactive"])
def test_session_invalidated(env, change):
    http, sessions, ids, _ = env
    login(http)
    with sessions() as db:
        session = db.scalar(select(ServerSession))
        if change == "expired": session.expires_at = auth.clock()-1
        elif change == "revoked": session.revoked = True
        else: db.get(Account, ids["lawyer"]).active = False
        db.commit()
    assert http.get("/api/v1/auth/me").status_code == 401


def test_rotation_and_csrf(env):
    http, sessions, ids, _ = env
    first = login(http)
    old = http.cookies.get(auth.COOKIE)
    second = login(http)
    assert http.cookies.get(auth.COOKIE) != old
    with sessions() as db:
        assert db.scalar(select(ServerSession).where(ServerSession.token_hash == auth.digest(old))).revoked
    for headers in [{}, {"origin": "https://evil.example", "x-csrf-token": second.json()["csrf_token"]},
                    {"origin": "https://firm.localhost", "x-csrf-token": first.json()["csrf_token"]}]:
        assert http.post("/api/v1/auth/logout", headers=headers).status_code == 403
    assert http.get("/api/v1/auth/me").status_code == 200


def test_portals_and_host_binding(env):
    http, sessions, ids, app = env
    assert login(http, "bank").status_code == 401
    assert login(http, origin="https://evil.example").status_code == 403
    assert login(http, user_id=ids["root"]).status_code == 422
    assert http.get("https://unknown.localhost/health").status_code == 403
    result = login(http)
    token = http.cookies.get(auth.COOKIE)
    # Explicit replay bypasses browser cookie restrictions; server still denies.
    assert http.get("https://client.localhost/api/v1/auth/me", headers={"Cookie": f"{auth.COOKIE}={token}"}).status_code == 403
    for host, name, org in [("client.localhost", "client", "halden"), ("bank.localhost", "bank", "castlegate")]:
        with TestClient(app, base_url=f"https://{host}") as external:
            assert login(external, name, f"https://{host}").status_code == 200
            assert external.get("/api/v1/auth/me").json()["organization"] == org
            assert external.get(f"/test/source/{ids['matter']}").status_code == 403


def test_no_header_identity_no_cache_no_cors(env):
    http, _, _, _ = env
    r = http.get("/api/v1/auth/me", headers={"X-Demo-User": "root", "X-Role": "legal_sme", "origin": "https://evil.example"})
    assert r.status_code == 401 and r.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in r.headers


def test_login_limit_and_public_gate(env, monkeypatch):
    http, _, _, _ = env
    for _ in range(10):
        assert http.post("/api/v1/auth/login", json={"username":"missing", "password":"wrong"}, headers={"origin":"https://firm.localhost"}).status_code == 401
    assert login(http).status_code == 429
    monkeypatch.setenv("KESTREL_ENV", "PUBLIC_DEMO")
    with pytest.raises(RuntimeError): create_app()


@pytest.mark.parametrize("mode", ["wrong_matter", "expired", "revoked", "future", "wall", "root", "role_revoked", "unknown_label"])
def test_policy_negative_routes(env, mode):
    http, sessions, ids, _ = env
    assert login(http, "root" if mode == "root" else "lawyer").status_code == 200
    path = f"/test/source/{ids['other'] if mode == 'wrong_matter' else ids['matter']}"
    with sessions() as db:
        grant = db.scalar(select(MatterAssignment).where(MatterAssignment.account_id == ids["lawyer"]))
        if mode == "expired": grant.expires_at = auth.clock()-1
        if mode == "revoked": grant.revoked = True
        if mode == "future": grant.starts_at = auth.clock()+3600
        if mode == "wall": db.add(EthicalWall(account_id=ids["lawyer"], matter_id=ids["matter"]))
        if mode == "role_revoked": db.execute(delete(RoleGrant).where(RoleGrant.account_id == ids["lawyer"]))
        db.commit()
    if mode == "unknown_label": path += "?label=unknown"
    assert http.get(path).status_code == 403


def test_clean_team_scope_and_live_revocation(env):
    http, sessions, ids, _ = env
    login(http)
    path = f"/test/source/{ids['matter']}?label=clean_team&scope=pricing"
    assert http.get(path).status_code == 403
    with sessions() as db:
        membership = CleanTeamMembership(account_id=ids["lawyer"], matter_id=ids["other"], scope="pricing", approved_by=ids["sme"], expires_at=auth.clock()+3600)
        db.add(membership); db.commit(); membership_id=membership.id
    assert http.get(path).status_code == 403
    with sessions() as db:
        db.get(CleanTeamMembership, membership_id).matter_id = ids["matter"]
        db.commit()
    assert http.get(path).status_code == 200
    with sessions() as db:
        db.get(CleanTeamMembership, membership_id).expires_at = auth.clock()-1
        db.commit()
    assert http.get(path).status_code == 403


def test_bank_release_and_independent_sme(env):
    from kestrel.repositories.identity import principal
    _, sessions, ids, _ = env
    with sessions() as db:
        actor = principal(db, db.get(Account, ids["bank"]), auth.clock())
        args = dict(action="read_release", matter=ids["matter"], now=auth.clock(), audience="castlegate", reviewed=True, published=True)
        assert policy.allowed(db, actor, **args)
        assert not policy.allowed(db, actor, **args, privileged=True)
        assert not policy.allowed(db, actor, **{**args, "reviewed":False})
        assert not policy.allowed(db, actor, **{**args, "published":False})
        assert not policy.allowed(db, actor, **{**args, "audience":"halden"})
        for name in ["root", "sme"]:
            actor = principal(db, db.get(Account, ids[name]), auth.clock())
            args = dict(action="approve_playbook", matter=ids["matter"], now=auth.clock())
            assert not policy.allowed(db, actor, **args, author_id=ids[name])
            assert policy.allowed(db, actor, **args, author_id=ids["lawyer"]) == (name == "sme")


def test_provision_rejects_cross_org_role(env):
    _, sessions, _, _ = env
    with sessions() as db:
        with pytest.raises(ValueError): provision(db,"bad","castlegate",["root_admin"],PASSWORD)
        with pytest.raises(ValueError): provision(db,"bad","firm",["root_admin"],"short")


def test_bad_payload_does_not_echo_password(env):
    http, _, _, _ = env
    r = login(http, actor_id="forged")
    assert r.status_code == 422 and PASSWORD not in r.text


def test_public_hosts_and_nonloopback_peer_denied(env):
    _, _, _, app = env
    with TestClient(app, base_url="https://kestrel-firm.ramijaloudi.com") as http:
        assert http.get("/health").status_code == 403
    with TestClient(app, base_url="https://firm.localhost", client=("198.51.100.5", 1234)) as http:
        assert http.get("/health").status_code == 403


def test_named_client_scope_needs_explicit_source_grant(env):
    from kestrel.repositories.identity import principal
    _, sessions, ids, _ = env
    with sessions() as db:
        db.add(CleanTeamMembership(account_id=ids["client"], matter_id=ids["matter"], scope="pricing", approved_by=ids["sme"], expires_at=auth.clock()+3600))
        db.commit()
        actor = principal(db, db.get(Account, ids["client"]), auth.clock())
        args = dict(action="read_source", matter=ids["matter"], now=auth.clock(), label="clean_team", scope="pricing")
        assert not policy.allowed(db, actor, **args)
        assert policy.allowed(db, actor, **args, explicitly_granted=True)
        assert not policy.allowed(db, actor, **args, explicitly_granted=True, privileged=True)
