"""Legacy attribute-only reference model for isolated tests; never production authorization."""
from kestrel.domain import Organization as O, Role as R, member_and_not_walled
from kestrel.repositories.identity import clean_scope


def allowed(db, actor, *, action, matter, now, label="ordinary", scope=None,
            explicitly_granted=False, audience=None, reviewed=False, published=False,
            privileged=False, author_id=None):
    if not member_and_not_walled(actor, matter):
        return False
    if label not in {"ordinary", "clean_team", "privileged"}:
        return False
    if label == "clean_team":
        if not scope or not clean_scope(db, actor.id, matter, scope, now):
            return False
    if action == "read_source":
        if actor.org == O.FIRM:
            return bool(actor.roles & {R.LAWYER, R.SME, R.ANTITRUST})
        return actor.org == O.CLIENT and label == "clean_team" and explicitly_granted and not privileged
    if action == "read_release":
        return (label != "clean_team" and reviewed and published and actor.org.value == audience
                and not (actor.org == O.BANK and (privileged or label == "privileged")))
    if action in {"approve_playbook", "approve_rerun"}:
        return actor.org == O.FIRM and R.SME in actor.roles and author_id is not None and author_id != actor.id
    return False
