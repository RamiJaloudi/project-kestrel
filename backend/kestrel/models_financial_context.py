"""Retained internal financial dimensions and unapproved extraction staging."""
from decimal import Decimal
from sqlalchemy import String,Integer,ForeignKey,UniqueConstraint,CheckConstraint,Index,Boolean
from sqlalchemy.orm import Mapped,mapped_column
from kestrel.models import Base,Identity,SourceWorkScope
from kestrel.financial_types import ExactFinancialDecimal

class FinancialFactContext(Identity,SourceWorkScope,Base):
    __tablename__='financial_fact_contexts'
    __table_args__=(UniqueConstraint('fact_id','revision',name='uq_financial_context_revision'),UniqueConstraint('created_by','request_key',name='uq_financial_context_request'),Index('ix_financial_context_fact','matter_id','fact_id','revision'),)
    fact_id:Mapped[str]=mapped_column(ForeignKey('financial_facts.id'))
    revision:Mapped[int]=mapped_column(Integer)
    previous_hash:Mapped[str|None]=mapped_column(String(64),nullable=True)
    fact_hash:Mapped[str]=mapped_column(String(64))
    reference_kind:Mapped[str]=mapped_column(String(16))
    reference_id:Mapped[str]=mapped_column(String(36))
    reference_snapshot:Mapped[str]=mapped_column(String(64))
    dimensions_json:Mapped[str]=mapped_column(String)
    provenance_json:Mapped[str]=mapped_column(String)
    content_hash:Mapped[str]=mapped_column(String(64))
    rationale:Mapped[str]=mapped_column(String(1000))
    created_by:Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at:Mapped[int]=mapped_column(Integer)
    request_key:Mapped[str]=mapped_column(String(128))
    input_hash:Mapped[str]=mapped_column(String(64))

class FinancialContextEvidence(Identity,SourceWorkScope,Base):
    __tablename__='financial_context_evidence'
    __table_args__=(UniqueConstraint('context_id','field','unit_number','start_offset','end_offset',name='uq_financial_context_evidence'),)
    context_id:Mapped[str]=mapped_column(ForeignKey('financial_fact_contexts.id'))
    field:Mapped[str]=mapped_column(String(32))
    unit_number:Mapped[int]=mapped_column(Integer)
    start_offset:Mapped[int]=mapped_column(Integer)
    end_offset:Mapped[int]=mapped_column(Integer)
    quote:Mapped[str]=mapped_column(String(2000))
    quote_hash:Mapped[str]=mapped_column(String(64))

class FinancialContextDecision(Identity,SourceWorkScope,Base):
    __tablename__='financial_context_decisions'
    __table_args__=(UniqueConstraint('context_id','operation',name='uq_financial_context_decision'),CheckConstraint("operation IN ('confirm','reject','revoke')",name='ck_financial_context_decision'),)
    context_id:Mapped[str]=mapped_column(ForeignKey('financial_fact_contexts.id'))
    operation:Mapped[str]=mapped_column(String(16))
    content_hash:Mapped[str]=mapped_column(String(64))
    actor_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    content_reviewed:Mapped[bool]=mapped_column(Boolean)
    rationale:Mapped[str]=mapped_column(String(1000))
    occurred_at:Mapped[int]=mapped_column(Integer)

class FinancialExtractionCandidate(Identity,SourceWorkScope,Base):
    __tablename__='financial_extraction_candidates'
    __table_args__=(UniqueConstraint('candidate_key',name='uq_financial_extraction_candidate'),CheckConstraint("state IN ('INCOMPLETE','READY_FOR_REVIEW')",name='ck_financial_candidate_state'),Index('ix_financial_candidate_source','matter_id','source_id','created_at'),)
    source_snapshot:Mapped[str]=mapped_column(String(64))
    extractor_version:Mapped[str]=mapped_column(String(96))
    anchor_key:Mapped[str]=mapped_column(String(256))
    candidate_key:Mapped[str]=mapped_column(String(64))
    raw_number:Mapped[str|None]=mapped_column(String(128),nullable=True)
    amount:Mapped[Decimal|None]=mapped_column(ExactFinancialDecimal(),nullable=True)
    amount_text:Mapped[str|None]=mapped_column(String(64),nullable=True)
    entity:Mapped[str|None]=mapped_column(String(160),nullable=True)
    metric:Mapped[str|None]=mapped_column(String(128),nullable=True)
    period_start:Mapped[str|None]=mapped_column(String(10),nullable=True)
    period_end:Mapped[str|None]=mapped_column(String(10),nullable=True)
    currency:Mapped[str|None]=mapped_column(String(3),nullable=True)
    scale:Mapped[str|None]=mapped_column(String(16),nullable=True)
    accounting_basis:Mapped[str|None]=mapped_column(String(128),nullable=True)
    consolidation_scope:Mapped[str|None]=mapped_column(String(128),nullable=True)
    state:Mapped[str]=mapped_column(String(32))
    dimensions_json:Mapped[str]=mapped_column(String)
    missing_json:Mapped[str]=mapped_column(String)
    evidence_json:Mapped[str]=mapped_column(String)
    provenance_json:Mapped[str]=mapped_column(String)
    normalized_json:Mapped[str|None]=mapped_column(String,nullable=True)
    content_hash:Mapped[str]=mapped_column(String(64))
    created_by:Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    created_at:Mapped[int]=mapped_column(Integer)
    request_key:Mapped[str]=mapped_column(String(128))
    input_hash:Mapped[str]=mapped_column(String(64))
