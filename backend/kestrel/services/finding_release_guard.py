"""Pure retained-finding checks for immutable audience packages.

No actor/source access is granted here. Historical rows, links and approval
hashes are never changed. Only the prefix through each exact pinned revision
contributes requirements; a future assessment cannot rewrite that prefix.
"""
import json
from sqlalchemy import select
from kestrel import models as m
from kestrel.services.documents import lineage as policy_lineage

REASON='RETAINED_FINDING_LINEAGE_UNBOUND'


class Unbound(ValueError):pass


def finding_row(db,policy_id):
    candidate=db.scalar(select(m.SourceFinding).where(m.SourceFinding.policy_id==policy_id))
    revision=db.scalar(select(m.LegalFindingRevision).where(m.LegalFindingRevision.policy_id==policy_id))
    if candidate is not None and revision is not None:raise Unbound()
    return revision or candidate


def pinned_prefix(db,key,pin):
    candidate=db.get(m.SourceFinding,pin)
    revision=db.get(m.LegalFindingRevision,pin)
    if candidate is not None:
        if revision is not None or candidate.id!=key:raise Unbound()
        return [candidate]
    if revision is None or revision.record_key!=key:raise Unbound()
    if revision.version_number<1 or revision.version_number>500:raise Unbound()
    rows=list(db.scalars(select(m.LegalFindingRevision).where(m.LegalFindingRevision.record_key==key,
        m.LegalFindingRevision.version_number<=revision.version_number).order_by(m.LegalFindingRevision.version_number).limit(501)))
    if len(rows)!=revision.version_number or rows[-1].id!=pin:raise Unbound()
    original=db.get(m.SourceFinding,revision.candidate_id) if revision.candidate_id else None
    if revision.candidate_id and (original is None or original.id!=key):raise Unbound()
    previous=None
    for number,row in enumerate(rows,1):
        if row.version_number!=number or row.previous_id!=previous or row.candidate_id!=revision.candidate_id:raise Unbound()
        previous=row.id
    return ([original] if original else [])+rows


def restrictions(policy,source_id):
    if policy.classification not in {'ordinary','privileged','clean_team'}:raise Unbound()
    result=set()
    if policy.classification=='privileged' or policy.resource_type=='legal_advice':result.add((source_id,'privileged',''))
    if policy.classification=='clean_team':
        if not policy.clean_team_scope:raise Unbound()
        result.add((source_id,'clean_team',policy.clean_team_scope))
    if policy.quarantined:result.add((source_id,'quarantined',''))
    if policy.ai_restricted:result.add((source_id,'ai_restricted',''))
    return result


def source_binding(db,policy):
    source=db.scalar(select(m.SourceVersion).where(m.SourceVersion.policy_id==policy.id))
    if source is not None:return source
    row=finding_row(db,policy.id) if policy.resource_type=='finding' else None
    return db.get(m.SourceVersion,row.source_id) if row is not None else None


def bound_sources(db,policy):
    source=source_binding(db,policy)
    if source is not None:return [source]
    ids=[p.id for p in policy_lineage(db,policy)]
    return list(db.scalars(select(m.SourceVersion).where(m.SourceVersion.policy_id.in_(ids))))


def recipient_set(db,policy_id):return set(db.scalars(select(m.PolicyRecipient.account_id).where(m.PolicyRecipient.policy_id==policy_id)))


def package_unbound(db,package,policy):
    own=policy_lineage(db,policy);actual={p.id:p for p in own}
    if any(p.matter_id!=policy.matter_id for p in own):raise Unbound()
    references=json.loads(package.references_json)
    if not isinstance(references,list) or len(references)>500:raise Unbound()
    nodes={p.id for p in own if p.resource_type=='finding'}
    prefixes=[];referenced=set();allowed_nodes=set()
    for reference in references:
        if not isinstance(reference,dict):raise Unbound()
        key=reference.get('finding_id');pin=reference.get('revision_id')
        if not isinstance(key,str) or not 1<=len(key)<=36:raise Unbound()
        # An original candidate ID is itself an immutable exact version. Never
        # infer a manual assessment's latest revision from an unpinned key.
        if pin is None and db.get(m.SourceFinding,key) is not None:pin=key
        if not isinstance(pin,str) or not 1<=len(pin)<=36 or key in referenced:raise Unbound()
        prefix=pinned_prefix(db,key,pin);pinned=prefix[-1]
        if pinned.policy_id not in nodes:raise Unbound()
        referenced.add(key);prefixes.extend(prefix);allowed_nodes.update(row.policy_id for row in prefix)
    if nodes-allowed_nodes:raise Unbound()
    # Coverage-only trackers legitimately have no finding references or nodes.
    if not prefixes:return False
    covered=set();actual_sources=set();current_recipients=None
    from kestrel.services.content_labels import policy_records,RESTRICTED
    for item in own:
        recipients=recipient_set(db,item.id)
        if recipients:current_recipients=recipients if current_recipients is None else current_recipients&recipients
        origins=bound_sources(db,item) if item.id!=policy.id else []
        for source in origins:
            if source.matter_id!=policy.matter_id:raise Unbound()
            covered.update(restrictions(item,source.id))
            if source.policy_id==item.id:
                if item.source_hash!=source.bytes_hash:raise Unbound()
                actual_sources.add(item.id)
                # Assertions are append-only protective records, including
                # contested labels. Their exact original-source node must remain
                # in the package snapshot; the canonical PDP enforces the labels.
                policy_records(db,item.id)
    for row in prefixes:
        source=db.get(m.SourceVersion,row.source_id);captured=db.get(m.DocumentPolicyVersion,row.policy_id)
        if source is None or captured is None or captured.resource_type!='finding' or source.matter_id!=policy.matter_id or captured.matter_id!=policy.matter_id:raise Unbound()
        bound=policy_lineage(db,captured)
        if source.policy_id not in {p.id for p in bound}:raise Unbound()
        for item in bound:
            if item.matter_id!=policy.matter_id:raise Unbound()
            origins=bound_sources(db,item)
            if not origins and restrictions(item,'unmapped'):return True
            for origin in origins:
                if not restrictions(item,origin.id)<=covered:return True
            old_recipients=recipient_set(db,item.id)
            if old_recipients and (current_recipients is None or not current_recipients<=old_recipients):return True
            original=db.scalar(select(m.SourceVersion).where(m.SourceVersion.policy_id==item.id))
            if original is not None:
                if item.id not in actual_sources or item.source_hash!=original.bytes_hash:return True
                # Missing protective original nodes cannot be replaced by a
                # different source carrying the same class/scope/name.
                if not restrictions(item,original.id)<=covered:return True
                records=policy_records(db,item.id)
                if any(set(record['labels'])&RESTRICTED for record in records) and item.id not in actual:return True
    return False


def denial(db,policy,lineage=None):
    """Return a safe reason for unbound package roots/ancestors, otherwise None."""
    try:
        bound=policy_lineage(db,policy) if lineage is None else lineage
        if not any(p.resource_type in {'report','tracker','export'} for p in bound):return None
        packages=list(db.scalars(select(m.ReleasePackage).where(m.ReleasePackage.policy_id.in_([p.id for p in bound]))))
        for package in packages:
            root=db.get(m.DocumentPolicyVersion,package.policy_id)
            if root is None or package_unbound(db,package,root):return REASON
    except (ValueError,TypeError,KeyError,AttributeError):return REASON
    return None


def pinned_policies(db,package):
    """Best-effort protective audit partitions; never returned as content."""
    result={}
    try:
        root=db.get(m.DocumentPolicyVersion,package.policy_id)
        for reference in json.loads(package.references_json):
            key=reference['finding_id'];pin=reference.get('revision_id') or key
            for row in pinned_prefix(db,key,pin):
                policy=db.get(m.DocumentPolicyVersion,row.policy_id)
                if policy:
                    bound=policy_lineage(db,policy)
                    if root is None or any(item.matter_id!=root.matter_id for item in bound):continue
                    for item in bound:result[item.id]=item
    except (ValueError,TypeError,KeyError,AttributeError):pass
    return list(result.values())
