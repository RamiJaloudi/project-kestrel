"""Versioned configuration is governed data, never a grant or executable tool."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from kestrel.schemas.disclosures import Strict

Id = Annotated[str, Field(min_length=1, max_length=36)]
Hash = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
AGENTS = ['coordinator','evidence','coverage','contracts','corporate','employment','ip_software','privacy','regulatory_clean_team','financial','synthesis','drafter','quality','citation_validator']
TOOLS = ['validate_current_scope','read_reviewed_findings','read_exact_evidence','validate_citations','write_internal_draft','request_attorney_review']
MODELS = {'offline': ['deterministic-reviewed-v1'], 'openai': ['gpt-5.4-mini-2026-03-17']}


class Definition(Strict):
    agent_kind: Literal['coordinator','evidence','coverage','contracts','corporate','employment','ip_software','privacy','regulatory_clean_team','financial','synthesis','drafter','quality','citation_validator']
    provider: Literal['offline','openai'] = 'offline'
    model: str = Field(min_length=1, max_length=96)
    prompt: str = Field(min_length=20, max_length=12000)
    tools: list[str] = Field(min_length=1, max_length=6)
    output_schema: Literal['ddr-typed-1'] = 'ddr-typed-1'
    timeout_seconds: int = Field(default=30, ge=1, le=60, strict=True)
    max_output_tokens: int = Field(default=1200, ge=1, le=2000, strict=True)
    total_tokens: int = Field(default=12000, ge=1, le=16000, strict=True)
    max_model_calls: int = Field(default=3, ge=1, le=3, strict=True)
    max_concurrency: int = Field(default=2, ge=1, le=2, strict=True)
    max_cost_cents: int = Field(default=200, ge=0, le=200, strict=True)
    @model_validator(mode='after')
    def manifests(self):
        if self.model not in MODELS[self.provider]:
            raise ValueError('Server-approved provider/model manifest required')
        if len(set(self.tools)) != len(self.tools) or set(self.tools) - set(TOOLS):
            raise ValueError('Distinct server-known read/draft/review-request tools required')
        return self


class Version(Strict):
    definition: Definition
    rationale: str = Field(min_length=10, max_length=1000)
    request_key: str = Field(min_length=8, max_length=128)
    expected_version_hash: Hash | None = None


class Create(Version):
    matter_id: Id
    name: str = Field(min_length=1, max_length=128)


class Action(Strict):
    operation: Literal['test','submit','approve','reject','publish','archive']
    content_hash: Hash
    rationale: str = Field(min_length=10, max_length=1000)
    content_reviewed: bool = Field(default=False, strict=True)


class ImpactDecision(Strict):
    operation: Literal['approve','reject','revoke']
    snapshot_hash: Hash
    target_hash: Hash
    rationale: str = Field(min_length=10, max_length=1000)


class Notification(Strict):
    operation: Literal['read','acknowledge']
