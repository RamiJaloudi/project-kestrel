"""Deterministic integrity/binding verification, not semantic/legal proof."""
from .schemas import CitationValidation, DraftReport, EvidenceBundle, RunSpec, ValidationIssue, digest


def validate_bundle(spec: RunSpec, bundle: EvidenceBundle) -> CitationValidation:
    issues = []
    if bundle.snapshot_hash != spec.snapshot_hash or bundle.config_hash != spec.config_hash:
        issues.append(ValidationIssue(code='snapshot_changed', reference=spec.run_id))
    for missing in set(spec.finding_refs) - {item.finding_ref for item in bundle.items}:
        issues.append(ValidationIssue(code='finding_unreviewed', reference=missing))
    for item in bundle.items:
        citation = item.citation
        if item.approved is not True:
            issues.append(ValidationIssue(code='finding_unreviewed', reference=item.id))
        if item.finding_ref not in spec.finding_refs or citation.finding_ref != item.finding_ref:
            issues.append(ValidationIssue(code='finding_mismatch', reference=item.id))
        if citation.evidence_id != item.id:
            issues.append(ValidationIssue(code='unknown_evidence', reference=item.id))
        if digest(item.unit_text) != item.unit_text_hash:
            issues.append(ValidationIssue(code='unit_hash', reference=item.id))
        if digest(citation.quote) != item.quote_hash:
            issues.append(ValidationIssue(code='quote_hash', reference=item.id))
        if citation.end > len(item.unit_text) or item.unit_text[citation.start:citation.end] != citation.quote:
            issues.append(ValidationIssue(code='span', reference=item.id))
    return CitationValidation(passed=not issues, issues=tuple(issues[:100]))


def validate_draft(spec: RunSpec, bundle: EvidenceBundle, draft: DraftReport) -> CitationValidation:
    initial = validate_bundle(spec, bundle)
    issues = list(initial.issues)
    by_id = {item.id: item for item in bundle.items}
    for claim in draft.claims:
        for citation in claim.citations:
            item = by_id.get(citation.evidence_id)
            if item is None:
                issues.append(ValidationIssue(code='unknown_evidence', reference=citation.evidence_id))
                continue
            if claim.finding_ref != item.finding_ref or citation.finding_ref != claim.finding_ref:
                issues.append(ValidationIssue(code='finding_mismatch', reference=item.id))
            if claim.severity != item.severity:
                issues.append(ValidationIssue(code='severity_changed', reference=item.id))
            if citation.source_bytes_hash != item.citation.source_bytes_hash or citation.source_text_hash != item.citation.source_text_hash:
                issues.append(ValidationIssue(code='source_hash', reference=item.id))
            if citation != item.citation:
                issues.append(ValidationIssue(code='citation_changed', reference=item.id))
    return CitationValidation(passed=not issues, issues=tuple(issues[:100]))
