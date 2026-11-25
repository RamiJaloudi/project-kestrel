"""Reinspect retained workbook bytes without rewriting their extraction or approvals."""
import json
from pathlib import PurePath
from fastapi import HTTPException
from kestrel.adapters.extraction import office_guard
from kestrel.adapters.spreadsheet_source import workbook

def scan(source):
    suffix=PurePath(source.file_name).suffix.lower()
    if suffix not in {'.xlsx','.xlsm'}:return None
    try:
        if not source.data or len(source.data)>3*1024*1024:raise ValueError()
        office_guard(source.data,'xl/workbook.xml',allow_inert_macros=suffix=='.xlsm')
        fresh=workbook(source.data,extended=True);old=json.loads(source.units_json)
        receipt=fresh[0]['workbook_safety']
        if not isinstance(old,list) or not old:raise ValueError()
        return {'receipt':receipt,'complete':old[0].get('workbook_safety')==receipt,'units':fresh}
    except Exception:raise HTTPException(409,'Workbook visibility cannot be established from retained bytes; explicit safe new-version intake required') from None

def handling(source,policy):
    info=scan(source)
    if info:
        receipt=info['receipt'];protected=receipt['sensitive_hidden']
        if protected and (policy.classification!='clean_team' or not policy.clean_team_scope or not policy.classification_confirmed):raise HTTPException(409,'Workbook hidden or opaque content requires reviewed scoped clean-team handling; no existing classification or approval was changed')
        if (protected or receipt['has_formulas']) and not info['complete']:raise HTTPException(409,'Legacy workbook lacks retained visibility evidence; explicitly ingest and review a new source version before disclosure')
    return info

def processing(source,policy):
    """Protective refusal, not a classification or an entitlement decision."""
    info=scan(source)
    if info:
        if not info['complete']:raise HTTPException(403,'Retained workbook visibility evidence is required before processing; source inspection remains available')
        if info['receipt']['sensitive_hidden'] and (policy.classification!='clean_team' or not policy.clean_team_scope or not policy.classification_confirmed):raise HTTPException(403,'Reviewed scoped workbook handling is required before processing; no source classification was changed')
    return info

def excluded(source,old_units):
    info=scan(source)
    if not info:return set()
    fresh={unit['locator']:unit for unit in info['units']};omitted=set()
    for unit in old_units:
        other=fresh.get(unit['locator'])
        metadata=unit['locator'] in {'Workbook worksheet manifest','Workbook retained hidden and opaque metadata'}
        if metadata:
            omitted.add(unit['number']);continue
        # No reinterpretation of old character coordinates or rounded values.
        if not other or other['text']!=unit['text']:raise HTTPException(409,'Retained workbook coordinates differ from safe literal scan; explicit new-version intake required')
        if other.get('hidden_content') or other.get('workbook_metadata') or any(cell.get('formula') is not None for cell in other.get('cells',[])):omitted.add(unit['number'])
    return omitted

def secrets(source):
    info=scan(source)
    if not info:return []
    values=[]
    for unit in info['units']:
        values.extend(unit.get('protected_literals',[]))
        for cell in unit.get('cells',[]):
            if cell.get('hidden'):values.append(cell['raw_value'])
            if cell.get('formula') is not None:values.extend([cell['formula'],cell.get('cached_value')])
    return sorted(set(value for value in values if isinstance(value,str) and value))
