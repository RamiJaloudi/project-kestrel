"""Additive document identity projection and retained VDR CSV staging; no source rewrites."""
from alembic import op
import sqlalchemy as sa
from uuid import uuid5,NAMESPACE_URL
revision='0026'
down_revision='0025'
branch_labels=None
depends_on=None
TABLES=['documents', 'document_version_links', 'vdr_mapping_profiles', 'vdr_import_batches', 'vdr_import_rows', 'document_sources']


def backfill(connection):
    rows=connection.execute(sa.text('SELECT id,matter_id,logical_key,created_at,bytes_hash FROM source_versions ORDER BY created_at,id')).mappings()
    for r in rows:
        document_id=str(uuid5(NAMESPACE_URL,'kestrel:document:'+r['matter_id']+':'+r['logical_key']))
        existing=connection.execute(sa.text('SELECT id FROM documents WHERE matter_id=:matter AND logical_key=:key'),{'matter':r['matter_id'],'key':r['logical_key']}).scalar()
        if existing is None:
            connection.execute(sa.text('INSERT INTO documents(id,matter_id,logical_key,created_at) VALUES (:id,:matter,:key,:at)'),{'id':document_id,'matter':r['matter_id'],'key':r['logical_key'],'at':r['created_at']})
        else:document_id=existing
        old=connection.execute(sa.text('SELECT document_id,matter_id,bytes_hash FROM document_version_links WHERE source_id=:id'),{'id':r['id']}).mappings().first()
        if old:
            if (old['document_id'],old['matter_id'],old['bytes_hash'])!=(document_id,r['matter_id'],r['bytes_hash']):raise RuntimeError('Document identity projection mismatch')
        else:connection.execute(sa.text('INSERT INTO document_version_links(source_id,document_id,matter_id,bytes_hash) VALUES (:source,:doc,:matter,:hash)'),{'source':r['id'],'doc':document_id,'matter':r['matter_id'],'hash':r['bytes_hash']})


def upgrade():
    op.create_table('documents',
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('logical_key',sa.String(96),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.UniqueConstraint('matter_id','logical_key',name='uq_document_matter_key'))
    op.create_table('document_version_links',
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False,primary_key=True),
        sa.Column('document_id',sa.String(36),sa.ForeignKey('documents.id'),nullable=False),
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('bytes_hash',sa.String(64),nullable=False))
    op.create_table('vdr_mapping_profiles',
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('name',sa.String(96),nullable=False),
        sa.Column('source_system',sa.String(96),nullable=False),
        sa.Column('version_number',sa.Integer(),nullable=False),
        sa.Column('mapping_json',sa.String(),nullable=False),
        sa.Column('delimiter',sa.String(1),nullable=False),
        sa.Column('author_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.UniqueConstraint('matter_id','name','version_number',name='uq_vdr_mapping_version'))
    op.create_table('vdr_import_batches',
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('profile_id',sa.String(36),sa.ForeignKey('vdr_mapping_profiles.id'),nullable=False),
        sa.Column('actor_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('request_key',sa.String(128),nullable=False),
        sa.Column('input_hash',sa.String(64),nullable=False),
        sa.Column('csv_hash',sa.String(64),nullable=False),
        sa.Column('raw_csv',sa.String(),nullable=False),
        sa.Column('file_name',sa.String(160),nullable=False),
        sa.Column('wave',sa.String(32),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.UniqueConstraint('actor_id','request_key',name='uq_vdr_batch_request'))
    op.create_table('vdr_import_rows',
        sa.Column('batch_id',sa.String(36),sa.ForeignKey('vdr_import_batches.id'),nullable=False),
        sa.Column('row_number',sa.Integer(),nullable=False),
        sa.Column('raw_json',sa.String(),nullable=False),
        sa.Column('mapped_json',sa.String(),nullable=False),
        sa.Column('errors_json',sa.String(),nullable=False),
        sa.Column('row_hash',sa.String(64),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.UniqueConstraint('batch_id','row_number',name='uq_vdr_batch_row'))
    op.create_table('document_sources',
        sa.Column('matter_id',sa.String(36),sa.ForeignKey('matters.id'),nullable=False),
        sa.Column('document_id',sa.String(36),sa.ForeignKey('documents.id'),nullable=False),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('source_versions.id'),nullable=False),
        sa.Column('import_row_id',sa.String(36),sa.ForeignKey('vdr_import_rows.id'),nullable=False),
        sa.Column('source_system',sa.String(96),nullable=False),
        sa.Column('source_external_id',sa.String(160),nullable=False),
        sa.Column('vdr_index_number',sa.String(160),nullable=False),
        sa.Column('folder_path',sa.String(1000),nullable=False),
        sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('id',sa.String(36),nullable=False,primary_key=True),
        sa.UniqueConstraint('import_row_id','source_id',name='uq_vdr_row_source'))
    backfill(op.get_bind())
    for table in TABLES:
        if op.get_bind().dialect.name=='sqlite':
            for operation in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'VDR identity record immutable'); END")
        else:op.execute(f'CREATE TRIGGER {table}_retained BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')


def downgrade():
    if any(op.get_bind().scalar(sa.text('SELECT count(*) FROM '+t)) for t in TABLES):raise RuntimeError('Retained document identity/import records prevent destructive downgrade')
    for table in reversed(TABLES):op.drop_table(table)
