"""Retained content labels; no source replacement or external disclosure bypass."""
from alembic import op
import sqlalchemy as sa
revision='0030'
down_revision='0029'
branch_labels=None
depends_on=None
TABLES=['content_label_assertions', 'content_label_decisions', 'content_label_impacts']

def upgrade():
    op.execute('\nCREATE TABLE content_label_assertions (\n\tversion_number INTEGER NOT NULL, \n\tlabels_json VARCHAR NOT NULL, \n\tlabel_scope VARCHAR(128), \n\tunit_number INTEGER, \n\tstart_offset INTEGER, \n\tend_offset INTEGER, \n\tevidence_hash VARCHAR(64) NOT NULL, \n\tsource_bytes_hash VARCHAR(64) NOT NULL, \n\tsource_text_hash VARCHAR(64) NOT NULL, \n\tprovenance_kind VARCHAR(24) NOT NULL, \n\tclassifier_version VARCHAR(64) NOT NULL, \n\tconfidence VARCHAR(16), \n\trationale VARCHAR(1000) NOT NULL, \n\tcreated_by VARCHAR(36) NOT NULL, \n\trequest_key VARCHAR(128) NOT NULL, \n\tinput_hash VARCHAR(64) NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\tcreated_at INTEGER NOT NULL, \n\tid VARCHAR(36) NOT NULL, \n\tmatter_id VARCHAR(36) NOT NULL, \n\tsource_id VARCHAR(36) NOT NULL, \n\tretained_classification VARCHAR(32) NOT NULL, \n\tretained_scope VARCHAR(128), \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_content_label_version UNIQUE (source_id, version_number), \n\tCONSTRAINT uq_content_label_request UNIQUE (created_by, request_key), \n\tFOREIGN KEY(created_by) REFERENCES accounts (id), \n\tFOREIGN KEY(matter_id) REFERENCES matters (id), \n\tFOREIGN KEY(source_id) REFERENCES source_versions (id)\n)\n\n')
    op.execute('\nCREATE TABLE content_label_decisions (\n\tassertion_id VARCHAR(36) NOT NULL, \n\tsequence INTEGER NOT NULL, \n\toperation VARCHAR(24) NOT NULL, \n\tactor_id VARCHAR(36) NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\trationale VARCHAR(1000) NOT NULL, \n\toccurred_at INTEGER NOT NULL, \n\tid VARCHAR(36) NOT NULL, \n\tmatter_id VARCHAR(36) NOT NULL, \n\tsource_id VARCHAR(36) NOT NULL, \n\tretained_classification VARCHAR(32) NOT NULL, \n\tretained_scope VARCHAR(128), \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_content_label_decision UNIQUE (assertion_id, sequence), \n\tFOREIGN KEY(assertion_id) REFERENCES content_label_assertions (id), \n\tFOREIGN KEY(actor_id) REFERENCES accounts (id), \n\tFOREIGN KEY(matter_id) REFERENCES matters (id), \n\tFOREIGN KEY(source_id) REFERENCES source_versions (id)\n)\n\n')
    op.execute('\nCREATE TABLE content_label_impacts (\n\tassertion_id VARCHAR(36) NOT NULL, \n\tpolicy_id VARCHAR(36) NOT NULL, \n\tkind VARCHAR(48) NOT NULL, \n\tcreated_at INTEGER NOT NULL, \n\tid VARCHAR(36) NOT NULL, \n\tmatter_id VARCHAR(36) NOT NULL, \n\tsource_id VARCHAR(36) NOT NULL, \n\tretained_classification VARCHAR(32) NOT NULL, \n\tretained_scope VARCHAR(128), \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_content_label_impact UNIQUE (assertion_id, policy_id), \n\tFOREIGN KEY(assertion_id) REFERENCES content_label_assertions (id), \n\tFOREIGN KEY(policy_id) REFERENCES document_policy_versions (id), \n\tFOREIGN KEY(matter_id) REFERENCES matters (id), \n\tFOREIGN KEY(source_id) REFERENCES source_versions (id)\n)\n\n')
    for table in TABLES:
        if op.get_bind().dialect.name=='sqlite':
            for operation in ['UPDATE','DELETE']:op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'content attribute evidence immutable'); END")
        else:op.execute(f'CREATE TRIGGER {table}_retained BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION kestrel_workflow_immutable()')

def downgrade():
    if any(op.get_bind().scalar(sa.text('SELECT count(*) FROM '+t)) for t in TABLES):raise RuntimeError('Retained label evidence prevents destructive downgrade; use forward repair or controlled archive recovery')
    for table in reversed(TABLES):op.drop_table(table)
