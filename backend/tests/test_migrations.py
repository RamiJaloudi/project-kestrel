from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect,text
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from kestrel.database import make_engine
from kestrel.models import Base


def test_upgrade_schema_matches_and_rollback(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("KESTREL_DATABASE_URL", url)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")
    engine = make_engine(url)
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
    command.check(cfg)
    engine.dispose()
    command.downgrade(cfg, "base")
    engine = make_engine(url)
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
    command.upgrade(cfg, "head")


def test_postgresql_schema_compiles():
    for table in Base.metadata.sorted_tables:
        assert "CREATE TABLE" in str(CreateTable(table).compile(dialect=postgresql.dialect()))


def test_number_migration_preserves_populated_legacy_registry(tmp_path,monkeypatch):
    url=f"sqlite:///{tmp_path/'legacy.db'}"
    monkeypatch.setenv('KESTREL_DATABASE_URL',url)
    cfg=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    command.upgrade(cfg,'0005')
    engine=make_engine(url)
    with engine.begin() as db:
        db.execute(text("INSERT INTO organizations(id,code) VALUES ('org','firm')"))
        db.execute(text("INSERT INTO accounts(id,username,password_hash,organization_id,active) VALUES ('actor','operator','test-only-hash','org',true)"))
        db.execute(text("INSERT INTO clients(id,name,created_by) VALUES ('client','Legacy synthetic client','actor')"))
        db.execute(text("INSERT INTO matters(id,name) VALUES ('matter','Legacy synthetic matter')"))
        db.execute(text("INSERT INTO matter_validations(matter_id,client_id,status,revision) VALUES ('matter','client','validated',1)"))
    engine.dispose()
    command.upgrade(cfg,'head')
    engine=make_engine(url)
    with engine.connect() as db:
        row=db.execute(text('SELECT * FROM vw_client_matter_validation')).mappings().one()
        assert row['matter_id']=='matter' and row['client_id']=='client'
        assert row['client_matter_number']=='900000-900000'
        assert not db.exec_driver_sql('PRAGMA foreign_key_check').all()
    engine.dispose()
