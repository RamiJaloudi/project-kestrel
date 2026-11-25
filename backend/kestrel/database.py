import os
import json
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


def make_engine(url: str):
    engine = create_engine(url, hide_parameters=True, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


def database_url():
    if os.environ.get("KESTREL_DATABASE_URL"):
        return os.environ["KESTREL_DATABASE_URL"]
    from kestrel.localenv import read_env
    local=read_env()
    if local.get('KESTREL_DATABASE_URL'):return local['KESTREL_DATABASE_URL']
    config=Path(__file__).resolve().parents[2]/'.runtime'/'database.json'
    if config.exists():
        return json.loads(config.read_text())['url']
    return "sqlite:///./kestrel-local.db"


def factory(engine):
    sessions=sessionmaker(engine, expire_on_commit=False)
    from kestrel.services.lifecycle import guard_flush
    event.listen(sessions,"before_flush",guard_flush)
    return sessions
