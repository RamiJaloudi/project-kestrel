"""Transient evidence/artifacts are separate from opaque checkpoint state."""
import hashlib
import json
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.:-]+$')]
Hash = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
Severity = Literal['low', 'medium', 'high', 'critical', 'unrated']


def canonical(value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode='json')
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256((value if isinstance(value, bytes) else value.encode('utf-8'))).hexdigest()


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class Limits(Strict):
    max_concurrency: int = Field(default=2, ge=1, le=2, strict=True)
    recursion_limit: int = Field(default=24, ge=12, le=40, strict=True)
    max_model_calls: int = Field(default=3, ge=1, le=3, strict=True)
    total_tokens: int = Field(default=12000, ge=1, le=16000, strict=True)
    max_output_tokens: int = Field(default=1200, ge=1, le=2000, strict=True)
    max_cost_cents: int = Field(default=200, ge=0, le=200, strict=True)


class RunSpec(Strict):
    run_id: Identifier
    requester_id: Identifier
    matter_id: Identifier
    graph_version: Literal['ddr-graph-1'] = 'ddr-graph-1'
    snapshot_hash: Hash
    config_hash: Hash
    finding_refs: tuple[Identifier, ...] = Field(min_length=1, max_length=50)
    deadline_epoch: int = Field(gt=0, strict=True)
    limits: Limits = Field(default_factory=Limits)
    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.finding_refs)) != len(self.finding_refs):
            raise ValueError('Distinct reviewed finding references required')
        return self


class Citation(Strict):
    evidence_id: Identifier
    finding_ref: Identifier
    source_version_id: Identifier
    source_bytes_hash: Hash
    source_text_hash: Hash
    unit: int = Field(ge=1, strict=True)
    start: int = Field(ge=0, strict=True)
    end: int = Field(ge=1, strict=True)
    quote: str = Field(min_length=1, max_length=8000)
    @model_validator(mode='after')
    def span(self):
        if self.end <= self.start:
            raise ValueError('Ordered Unicode offsets required')
        return self


class EvidenceItem(Strict):
    id: Identifier
    finding_ref: Identifier
    approved: Literal[True] = True
    severity: Severity
    summary: str = Field(min_length=1, max_length=4000)
    citation: Citation
    unit_text: str = Field(max_length=100000)
    unit_text_hash: Hash
    quote_hash: Hash


class EvidenceBundle(Strict):
    snapshot_hash: Hash
    config_hash: Hash
    items: tuple[EvidenceItem, ...] = Field(min_length=1, max_length=50)
    @model_validator(mode='after')
    def bounded(self):
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError('Distinct evidence references required')
        if sum(len(item.unit_text) + len(item.summary) for item in self.items) > 120000:
            raise ValueError('Transient evidence context exceeded bounds')
        return self


class Claim(Strict):
    finding_ref: Identifier
    text: str = Field(min_length=1, max_length=4000)
    severity: Severity
    citations: tuple[Citation, ...] = Field(min_length=1, max_length=8)


class SpecialistResult(Strict):
    kind: Literal['specialist'] = 'specialist'
    claims: tuple[Claim, ...] = Field(min_length=1, max_length=50)


class DraftReport(Strict):
    kind: Literal['draft'] = 'draft'
    title: str = Field(min_length=1, max_length=160)
    claims: tuple[Claim, ...] = Field(min_length=1, max_length=50)
    status: Literal['draft_ai_assisted'] = 'draft_ai_assisted'


class QualityReview(Strict):
    kind: Literal['quality'] = 'quality'
    passed: bool = Field(strict=True)
    issues: tuple[Literal['unsupported_claim', 'missing_context', 'contradiction', 'novel_issue', 'scope_gap'], ...] = Field(default=(), max_length=50)
    @model_validator(mode='after')
    def consistent(self):
        if self.passed and self.issues:
            raise ValueError('Quality issues cannot be silently passed')
        return self


class ValidationIssue(Strict):
    code: Literal['snapshot_changed', 'finding_unreviewed', 'source_hash', 'unit_hash', 'quote_hash', 'span', 'unknown_evidence', 'finding_mismatch', 'severity_changed', 'citation_changed']
    reference: Identifier


class CitationValidation(Strict):
    kind: Literal['validation'] = 'validation'
    passed: bool = Field(strict=True)
    issues: tuple[ValidationIssue, ...] = Field(default=(), max_length=100)


Artifact = SpecialistResult | DraftReport | QualityReview | CitationValidation


class ArtifactRef(Strict):
    id: Identifier
    kind: Literal['specialist', 'draft', 'quality', 'validation']
    content_hash: Hash
    creator_id: Identifier


class ApprovalReceipt(Strict):
    id: Identifier
    decision: Literal['approve', 'reject']
    reviewer_id: Identifier
    draft_hash: Hash
    snapshot_hash: Hash
    config_hash: Hash


class Usage(Strict):
    input_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)
    cost_cents: int = Field(ge=0, strict=True)


class ProviderResult(Strict):
    artifact: Artifact
    usage: Usage
