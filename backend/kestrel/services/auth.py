"""Local account authentication; client headers never assert identity."""
import hashlib
import hmac
import secrets
import time
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException
from sqlalchemy import select,text,case,update,delete
from kestrel.deployment_settings import LOCAL_HOSTS,settings_for
from kestrel.models import Account, Organization, ServerSession, LoginThrottle, AuditEvent
from kestrel.repositories.identity import principal

HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))
COOKIE = "__Host-kestrel_session"
USERNAME_COOKIE='__Host-kestrel_username'
SESSION_SECONDS=1800
REMEMBER_SECONDS=30*86400
HOSTS = dict(LOCAL_HOSTS)  # Backwards-compatible LOCAL constant, never mutated.


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def clock():
    return int(time.time())


def portal(request):
    settings=settings_for(request);host = request.url.hostname
    if host not in settings.hosts or settings.hosts[host] is None:
        raise HTTPException(403, "Portal denied")
    return host, settings.hosts[host]


def same_origin(request):
    settings=settings_for(request)
    allowed=settings.origin_matches(request.headers.get('origin'),request.url.hostname) if settings.public else request.headers.get('origin')==f'{request.url.scheme}://{request.url.netloc}'
    if request.url.scheme != "https" or not allowed:
        raise HTTPException(403, "Request origin denied")


def audit(db, action, outcome, actor_id=None, *, category="administrative",matter_id=None,object_id=None,clean_team_scope=None,correlation_id=None):
    db.add(AuditEvent(occurred_at=clock(), action=action, outcome=outcome, actor_id=actor_id,
           category=category,matter_id=matter_id,object_id=object_id,clean_team_scope=clean_team_scope,correlation_id=correlation_id))


def authenticate(db, request, *, check_csrf=True):
    host, org_code = portal(request)
    token = request.cookies.get(COOKIE, "")
    session = db.scalar(select(ServerSession).where(ServerSession.token_hash == digest(token))) if token else None
    if session is None or session.revoked or session.expires_at <= clock():
        raise HTTPException(401, "Authentication required")
    account = db.get(Account, session.account_id)
    if account is None or not account.active:
        raise HTTPException(401, "Authentication required")
    org = db.get(Organization, account.organization_id)
    if session.host != host or org.code != org_code:
        raise HTTPException(403, "Portal denied")
    if check_csrf and request.method not in {"GET", "HEAD", "OPTIONS"}:
        same_origin(request)
        if not hmac.compare_digest(session.csrf_hash, digest(request.headers.get("x-csrf-token", ""))):
            raise HTTPException(403, "CSRF check failed")
    return account, session, principal(db, account, clock())


def csrf_for_token(token):
    return hmac.new(token.encode(),b'kestrel-session-csrf-v1',hashlib.sha256).hexdigest()


def restore(db,request):
    # Bootstrap CSRF after reopening a page using only an authenticated cookie
    # AND exact HTTPS Origin. Never expose this exception to ordinary routes.
    same_origin(request)
    actor=authenticate(db,request,check_csrf=False)
    csrf=csrf_for_token(request.cookies[COOKIE])
    if not hmac.compare_digest(actor[1].csrf_hash,digest(csrf)):
        actor[1].csrf_hash=digest(csrf)
        audit(db,'session.restore','allowed',actor[0].id)
        db.commit()
    return actor,csrf


def login(db, request, username, password, remember_me=False):
    host, org_code = portal(request)
    same_origin(request)
    now = clock()
    username = username.strip().casefold()
    peer=request.client.host if request.client else 'unknown'
    keys = [digest("account:" + username), digest("peer:" + peer),digest('peer-failures:'+peer)]
    if settings_for(request).public:
        expired=list(db.scalars(select(LoginThrottle.key).where(LoginThrottle.window_start<now-900).limit(32)))
        if expired:db.execute(delete(LoginThrottle).where(LoginThrottle.key.in_(expired),LoginThrottle.window_start<now-900))
    for key in sorted(keys):
        db.execute(text('INSERT INTO login_throttles(key,attempts,window_start) VALUES (:key,0,:now) ON CONFLICT(key) DO NOTHING'),{'key':key,'now':now})
        expired=LoginThrottle.window_start<=now-900;increment=0 if key==keys[2] else 1
        changed=db.execute(update(LoginThrottle).where(LoginThrottle.key==key,(expired)|(LoginThrottle.attempts<(100 if key==keys[1] else 10))).values(
            attempts=case((expired,increment),else_=LoginThrottle.attempts+increment),window_start=case((expired,now),else_=LoginThrottle.window_start)))
        if changed.rowcount!=1:
            audit(db, "login", "throttled")
            db.commit()
            raise HTTPException(429, "Try again later")
    account = db.scalar(select(Account).where(Account.username == username).with_for_update())
    try:
        valid = HASHER.verify(account.password_hash if account else DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        valid = False
    org = db.get(Organization, account.organization_id) if account else None
    if not valid or not account or not account.active or org.code != org_code:
        db.get(LoginThrottle,keys[2]).attempts+=1
        audit(db, "login", "denied")
        db.commit()
        raise HTTPException(401, "Invalid credentials or portal")
    if HASHER.check_needs_rehash(account.password_hash):
        account.password_hash = HASHER.hash(password)
    # Account lockout measures consecutive failures; peer budget also caps successful logins.
    db.get(LoginThrottle,keys[0]).attempts=0
    old_token = request.cookies.get(COOKIE)
    if old_token:
        old = db.scalar(select(ServerSession).where(ServerSession.token_hash == digest(old_token)))
        if old:
            old.revoked = True
    token=secrets.token_urlsafe(32)
    csrf=csrf_for_token(token)
    db.add(ServerSession(token_hash=digest(token), csrf_hash=digest(csrf), account_id=account.id,
                         host=host, expires_at=now + (REMEMBER_SECONDS if remember_me else SESSION_SECONDS)))
    audit(db, "login", "allowed", account.id)
    db.commit()
    return token, csrf
