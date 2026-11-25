"""SQL-backed person restrictions. Relationships describe scope; they never grant access."""
from sqlalchemy import text,select
from kestrel.models import MatterValidation

RELATIONSHIPS={
    'relationship_partner':'Client relationship partner',
    'matter_team':'Matter team member',
    'matter_lead':'Matter lead',
    'client_contact':'Client legal contact',
    'bank_adviser':'Bank adviser',
    'external_adviser':'External adviser',
    'outside_business_clean_team':'Named person outside the business (designation only)',
    'restricted_interest':'Conflicts-confirmed restricted interest'}

def state(db,account_id,roles,now):
    rows=[dict(row) for row in db.execute(text('SELECT * FROM vw_person_wall_entries WHERE starts_at<=:now AND (expires_at IS NULL OR expires_at>:now) AND (account_id IS NULL OR account_id=:account)'),{'now':now,'account':account_id}).mappings()]
    relations=[row for row in rows if row['entry_type']=='relationship' and row['account_id']==account_id]
    client={};matter={}
    def deny(row):
        bucket=matter if row['matter_id'] else client;key=row['matter_id'] or row['client_id']
        bucket.setdefault(key,[]).append(row['id'])
    for row in relations:
        if row['relationship_kind']=='restricted_interest':deny(row)
    for row in rows:
        if row['entry_type']!='restriction':continue
        if row['account_id'] and row['account_id']!=account_id:continue
        if row['role_name'] and row['role_name'] not in roles:continue
        if row['relationship_kind'] and not any(r['client_id']==row['client_id'] and r['relationship_kind']==row['relationship_kind'] and (r['matter_id'] is None or r['matter_id']==row['matter_id']) for r in relations):continue
        deny(row)
    denied_matters=set(matter)
    if client:denied_matters.update(db.scalars(select(MatterValidation.matter_id).where(MatterValidation.client_id.in_(client))))
    return {'client':client,'matter':matter,'relationships':relations,'denied_matters':denied_matters}
