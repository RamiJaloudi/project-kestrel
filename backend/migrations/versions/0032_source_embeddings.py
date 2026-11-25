"""Immutable source-scoped embedding cache; no grants or provider calls during migration."""
from alembic import op
import sqlalchemy as sa
revision='0032'
down_revision='0031'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('\nCREATE TABLE source_embeddings (\n\tsource_snapshot VARCHAR(64) NOT NULL, \n\tunit_number INTEGER NOT NULL, \n\tstart_offset INTEGER NOT NULL, \n\tend_offset INTEGER NOT NULL, \n\ttext_hash VARCHAR(64) NOT NULL, \n\tmodel_version VARCHAR(96) NOT NULL, \n\tvector_json VARCHAR NOT NULL, \n\tvector_hash VARCHAR(64) NOT NULL, \n\tcreated_by VARCHAR(36) NOT NULL, \n\toperation_id VARCHAR(36) NOT NULL, \n\tcreated_at INTEGER NOT NULL, \n\tid VARCHAR(36) NOT NULL, \n\tmatter_id VARCHAR(36) NOT NULL, \n\tsource_id VARCHAR(36) NOT NULL, \n\tretained_classification VARCHAR(32) NOT NULL, \n\tretained_scope VARCHAR(128), \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_source_embedding UNIQUE (source_id, source_snapshot, unit_number, start_offset, end_offset, model_version), \n\tFOREIGN KEY(created_by) REFERENCES accounts (id), \n\tFOREIGN KEY(operation_id) REFERENCES ai_operations (id), \n\tFOREIGN KEY(matter_id) REFERENCES matters (id), \n\tFOREIGN KEY(source_id) REFERENCES source_versions (id)\n)\n\n')
    if op.get_bind().dialect.name=='sqlite':
        for operation in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER source_embeddings_no_{operation.lower()} BEFORE {operation} ON source_embeddings BEGIN SELECT RAISE(ABORT,'embedding evidence immutable'); END")
    else:op.execute('CREATE TRIGGER source_embeddings_retained BEFORE UPDATE OR DELETE ON source_embeddings FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')

def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM source_embeddings')):raise RuntimeError('Retained embeddings prevent destructive downgrade')
    op.drop_table('source_embeddings')
