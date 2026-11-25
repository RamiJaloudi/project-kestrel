"""Small pure domain example. All IDs, roles and records are synthetic.

These functions are architectural reference and useful unit tests. They are NOT an
identity provider, database, access control enforcement layer for deployed services,
or a replacement for a transactionally safe reanalysis service.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json


class Organization(str, Enum):
    FIRM = "firm"
    CLIENT = "halden"
    BANK = "castlegate"


class Role(str, Enum):
    ROOT_ADMIN = "root_admin"
    LAWYER = "firm_lawyer"
    SME = "legal_sme"
    ANTITRUST = "antitrust_counsel"
    CLIENT = "client_user"
    BANK = "bank_analyst"
    AUDITOR = "matter_auditor"
    CLEAN_AUDITOR = "clean_team_auditor"
    SECURITY = "security_approver"
    CONFLICTS = "conflicts_approver"


@dataclass(frozen=True)
class Principal:
    id: str
    org: Organization
    roles: frozenset[Role] = field(default_factory=frozenset)
    matters: frozenset[str] = field(default_factory=frozenset)
    walls: frozenset[str] = field(default_factory=frozenset)
    clean_team_scopes: frozenset[str] = field(default_factory=frozenset)
    client_walls: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Document:
    id: str
    matter: str
    label: str = "ordinary"
    clean_team_scope: str | None = None


@dataclass(frozen=True)
class ReleasedArtifact:
    id: str
    matter: str
    audiences: frozenset[Organization]
    approved_by_attorney: bool
    published: bool
    privileged: bool = False
    clean_team_derived: bool = False
    sanitized: bool = False
    approved_by_antitrust: bool = False


def member_and_not_walled(actor: Principal, matter: str) -> bool:
    return matter in actor.matters and matter not in actor.walls


def can_view_original(actor: Principal, document: Document) -> bool:
    # External parties never get general source-document access in this example.
    if actor.org != Organization.FIRM or not member_and_not_walled(actor, document.matter):
        return False
    if not actor.roles.intersection({Role.LAWYER, Role.SME, Role.ANTITRUST}):
        return False  # ROOT_ADMIN alone cannot read matter data
    if document.label.startswith("clean_team"):
        return bool(document.clean_team_scope and document.clean_team_scope in actor.clean_team_scopes)
    return True


def can_view_released(actor: Principal, artifact: ReleasedArtifact) -> bool:
    if not member_and_not_walled(actor, artifact.matter):
        return False
    if not artifact.published or not artifact.approved_by_attorney:
        return False
    if actor.org not in artifact.audiences:
        return False
    if actor.org == Organization.BANK and artifact.privileged:
        return False
    if artifact.clean_team_derived and not (artifact.sanitized and artifact.approved_by_antitrust):
        return False
    return True


def can_approve_legal_playbook(actor: Principal, author_id: str, matter: str) -> bool:
    return (actor.id != author_id and actor.org == Organization.FIRM
            and Role.SME in actor.roles and member_and_not_walled(actor, matter))


@dataclass(frozen=True)
class ImpactSnapshot:
    id: str
    matter: str
    source_playbook: str
    target_playbook: str
    document_version_ids: tuple[str, ...]
    approved_finding_ids: tuple[str, ...]
    released_artifact_ids: tuple[str, ...]
    clean_team_document_version_ids: tuple[str, ...] = ()
    diff_hash: str = ""
    target_version_hash: str = ""

    def digest(self) -> str:
        data = {
            "id": self.id,
            "matter": self.matter,
            "source_playbook": self.source_playbook,
            "target_playbook": self.target_playbook,
            "document_version_ids": sorted(self.document_version_ids),
            "approved_finding_ids": sorted(self.approved_finding_ids),
            "released_artifact_ids": sorted(self.released_artifact_ids),
            "clean_team_document_version_ids": sorted(self.clean_team_document_version_ids),
            "diff_hash": self.diff_hash,
            "target_version_hash": self.target_version_hash
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def counts(self) -> dict[str, int]:
        return {"affected_document_versions": len(self.document_version_ids),
                "approved_findings": len(self.approved_finding_ids),
                "released_artifacts": len(self.released_artifact_ids),
                "clean_team_document_versions": len(self.clean_team_document_version_ids)}


class StaleImpactError(ValueError):
    pass


class AccessDenied(PermissionError):
    pass


@dataclass(frozen=True)
class ApprovalDecision:
    request_id: str
    actor_id: str
    outcome: str
    rationale: str
    impact_digest: str
    scope: str


def decide_reanalysis(*, actor: Principal, playbook_author_id: str,
                      impact: ImpactSnapshot, supplied_digest: str, request_id: str,
                      outcome: str, rationale: str, scope: str = "unrestricted") -> ApprovalDecision:
    """Validate *in-memory* predicates. Real service MUST recheck in a DB transaction."""
    if not member_and_not_walled(actor, impact.matter) or actor.org != Organization.FIRM:
        raise AccessDenied("Matter access denied")
    if Role.SME not in actor.roles or actor.id == playbook_author_id:
        raise AccessDenied("Independent legal SME required")
    if supplied_digest != impact.digest():
        raise StaleImpactError("Impact snapshot changed; refresh before decision")
    if outcome not in {"approve", "reject"} or not rationale.strip():
        raise ValueError("A valid decision and reason are required")
    if scope not in {"unrestricted", "all_including_clean_team"}:
        raise ValueError("Unsupported scope")
    if outcome == "approve" and scope == "all_including_clean_team":
        # This pure helper models a simple gate; production needs granular task approval.
        if not impact.clean_team_document_version_ids or "KESTREL-CUSTOMER-PRICING" not in actor.clean_team_scopes:
            raise AccessDenied("No authorized clean-team scope")
    return ApprovalDecision(request_id, actor.id, outcome, rationale.strip(), supplied_digest, scope)


def compare_playbook_rules(old_rules: list[dict], new_rules: list[dict]) -> list[dict]:
    """Deterministic, exact top-level rule-field diff suitable for a local fixture.

    Production must also track nested JSON paths and human-reviewed materiality.
    """
    old = {rule["rule_id"]: rule for rule in old_rules}
    new = {rule["rule_id"]: rule for rule in new_rules}
    results: list[dict] = []
    for rule_id in sorted(set(old) | set(new)):
        if rule_id not in old:
            results.append({"rule_id": rule_id, "change": "added", "old": None, "new": new[rule_id]})
        elif rule_id not in new:
            results.append({"rule_id": rule_id, "change": "removed", "old": old[rule_id], "new": None})
        elif old[rule_id] != new[rule_id]:
            for field_name in sorted(set(old[rule_id]) | set(new[rule_id])):
                if old[rule_id].get(field_name) != new[rule_id].get(field_name):
                    results.append({"rule_id": rule_id, "change": "modified", "field": field_name,
                                    "old": old[rule_id].get(field_name),
                                    "new": new[rule_id].get(field_name)})
    return results


@dataclass(frozen=True)
class Notification:
    id: str
    recipient_id: str
    state: str = "unread"
    task_state: str = "awaiting_decision"

    def mark_read(self) -> "Notification":
        from dataclasses import replace
        return replace(self, state="read")

    def acknowledge(self) -> "Notification":
        from dataclasses import replace
        return replace(self, state="acknowledged")
