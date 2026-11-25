"""Deterministic staging from retained literal evidence; no inference or execution."""
import re
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from kestrel.adapters.extraction import canonical
from kestrel.adapters.financial import number,base_amount,canonical_amount
from kestrel.schemas.financial_context import Dimensions

VERSION='literal-financial-stage-1'
CORE=['entity','metric','period_label','period_start','period_end','currency','scale','scale_label','accounting_basis','consolidation_scope']
RICH=['instruments','precision','sign','calendar','period','restatement']
HEADERS={'amount',*CORE,'decimal_mark','numeric_notation','instrument_scheme','instrument_id','instrument_venue','precision_kind','precision_value','precision_label','sign_convention','calendar_kind','calendar_label','period_kind','restatement_kind','restatement_label'}

def span(unit,start,end,field):
    return {'field':field,'unit':unit['number'],'start':start,'end':end,'quote':unit['text'][start:end]}

def sign(raw):
    token=raw.strip()
    return 'parentheses' if token.startswith('(') and token.endswith(')') else 'minus' if token.startswith('-') else 'plus' if token.startswith('+') else 'unsigned'

def dimensions(values,raw):
    result={}
    if values.get('instrument_scheme') and values.get('instrument_id'):
        result['instruments']={'status':'KNOWN','identifiers':[{'scheme':values['instrument_scheme'],'value':values['instrument_id'],'venue':values.get('instrument_venue') or None}]}
    if values.get('precision_kind') and values.get('precision_label'):
        result['precision']={'status':'KNOWN','kind':values['precision_kind'],'value':values.get('precision_value') or None,'label':values['precision_label']}
    if values.get('sign_convention') and raw:result['sign']={'status':'KNOWN','presentation':sign(raw),'convention':values['sign_convention']}
    for field in ['calendar','period','restatement']:
        if values.get(field+'_kind') and values.get(field+'_label'):result[field]={'status':'KNOWN','kind':values[field+'_kind'],'label':values[field+'_label']}
    # Invalid declarations become explicit missing fields, never guessed values.
    safe=Dimensions().model_dump(mode='json')
    for field,value in result.items():
        try:safe[field]=getattr(Dimensions.model_validate({field:value}),field).model_dump(mode='json')
        except ValueError:pass
    return safe

def finish(anchor,values,raw,amount,dims,refs,provenance):
    if len(refs)>64 or sum(len(ref['quote']) for ref in refs)>8000:raise HTTPException(413,'Candidate evidence exceeds the bounded 8000-character review limit; no partial stage was written')
    known={field:values.get(field) or None for field in CORE};missing=[]
    for field,value in known.items():
        if value is None:missing.append(field)
    for field,bound in [('entity',160),('metric',128),('period_label',128),('scale_label',64),('accounting_basis',128),('consolidation_scope',128)]:
        if known[field] and len(known[field])>bound:known[field]=None;missing.append(field)
    for field in ['period_start','period_end']:
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',known[field] or ''):raise ValueError()
            date.fromisoformat(known[field])
        except ValueError:known[field]=None;missing.append(field)
    if known['period_start'] and known['period_end'] and known['period_start']>known['period_end']:known['period_end']=None;missing.append('period_end')
    if not re.fullmatch(r'[A-Z]{3}',known['currency'] or ''):known['currency']=None;missing.append('currency')
    if known['scale'] not in {'1','1000','1000000'}:known['scale']=None;missing.append('scale')
    if amount is None:missing.append('amount')
    for field in RICH:
        if dims[field]['status']=='UNKNOWN':missing.append(field)
    for identifier in dims['instruments']['identifiers']:
        if identifier['scheme']=='OTHER' or identifier['scheme']=='TICKER' and not identifier['venue']:missing.append('instrument_identity')
    missing=sorted(set(missing));text=canonical_amount(amount) if amount is not None else None
    return {'anchor_key':anchor,'raw_number':raw if raw and len(raw)<=128 else None,'amount_text':text,**{field:known[field] for field in ['entity','metric','period_start','period_end','currency','scale','accounting_basis','consolidation_scope']},
        'state':'INCOMPLETE' if missing else 'READY_FOR_REVIEW','dimensions':dims,'missing':missing,'evidence':refs,'provenance':provenance,
        'normalized':None if missing else {**known,'amount_text':text,'dimensions':dims,'approval':'UNAPPROVED','source_evidence':refs}}

def literal_rows(units):
    result=[];sheets={}
    for unit in units:
        if 'cells' in unit:sheets.setdefault(unit.get('sheet'),[]).append(unit)
    for sheet,rows in sheets.items():
        # Exact first-row header vocabulary only. No positional/semantic guessing.
        rows.sort(key=lambda u:u['row']);header=rows[0];columns={};header_refs={};valid=True
        for cell in header['cells']:
            name=cell['raw_value']
            if cell.get('formula') is not None or name not in HEADERS or name in columns:valid=False;break
            columns[name]=cell['column'];header_refs[name]=span(header,cell['start'],cell['end'],name+'.header')
        if not valid or 'amount' not in columns:continue
        for unit in rows[1:]:
            by={cell['column']:cell for cell in unit['cells']};values={};refs=[]
            for name,col in columns.items():
                cell=by.get(col)
                if cell is None or cell.get('formula') is not None:continue
                values[name]=cell['raw_value'];refs.extend([header_refs[name],span(unit,cell['start'],cell['end'],name)])
            cell=by.get(columns['amount']);raw=values.pop('amount',None);amount=None
            # XML numeric cells declare XML decimal syntax; strings need BOTH
            # explicit syntax fields. A style or cached formula is not evidence.
            mark='.' if cell and cell.get('value_kind')=='n' else values.get('decimal_mark')
            notation=('scientific' if raw and re.search('[eE]',raw) else 'decimal') if cell and cell.get('value_kind')=='n' else values.get('numeric_notation')
            try:
                xml_ok=not cell or cell.get('value_kind')!='n' or raw is not None and re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?',raw)
                if xml_ok and raw is not None and mark in {'.',','} and notation in {'decimal','scientific'}:amount=base_amount(number(raw,mark,scientific=notation=='scientific'),values.get('scale'))
            except HTTPException:pass
            dims=dimensions(values,raw)
            result.append(finish('sheet:'+str(sheet)+':row:'+str(unit['row']),values,raw,amount,dims,refs,{'origin':'literal_exact_header_template','extractor':VERSION,'numeric_syntax':{'decimal_mark':mark,'numeric_notation':notation},'confidence':{'status':'UNKNOWN'},'formula_policy':'Formula cells and cached values are never used; missing declarations stay UNKNOWN.'}))
    return result

def xbrl(units):
    result=[]
    for unit in units:
        item=unit.get('structured_financial')
        if not item or not item['numeric']:continue
        context=item['context'];period=context['period'];measure=item.get('unit') or {};currency=None;amount=None
        numerators=measure.get('numerator',[])
        if len(numerators)==1 and not measure.get('denominator') and numerators[0].startswith('{http://www.xbrl.org/2003/iso4217}'):
            currency=numerators[0].split('}',1)[1]
        # XBRL scale and declared transform have already been applied exactly by
        # the retained parser. No second scaling or taxonomy mapping occurs.
        if item['decimal_value'] is not None:
            try:amount=base_amount(Decimal(item['decimal_value']),'1')
            except HTTPException:pass
        value={'entity':context['entity'],'metric':item['concept'],'period_start':period.get('startDate') or period.get('instant'),'period_end':period.get('endDate') or period.get('instant'),'currency':currency,'scale':'1','scale_label':'XBRL normalized unit'}
        dims=Dimensions().model_dump(mode='json');accuracy='decimals' if item['decimals'] is not None else 'precision' if item['precision'] is not None else None
        if accuracy:dims['precision']={'status':'KNOWN','kind':accuracy,'value':item[accuracy],'label':accuracy+'='+item[accuracy]}
        if 'instant' in period:dims['period']={'status':'KNOWN','kind':'instant','label':period['instant']}
        # Entity identifiers are NOT instrument IDs. A 12-month duration does
        # not establish a fiscal year, annual reporting or original/restated.
        refs=[span(unit,0,len(unit['text']),'structured_xbrl_fact')]
        result.append(finish('xbrl:'+str(item['fact_index']),value,item['raw_value'] or None,amount,dims,refs,{'origin':'retained_xbrl_attributes','extractor':VERSION,'structured_financial':item,'confidence':{'status':'UNKNOWN'},'taxonomy_validation':'NOT_PERFORMED','missing_semantics':'No instrument, accounting, consolidation, fiscal calendar, sign convention or restatement inference.'}))
    return result

def extract(units,extractor,limit):
    result=literal_rows(units) if extractor=='literal_rows_v1' else xbrl(units)
    if len(result)>limit:raise HTTPException(413,'Extraction exceeds the selected bounded candidate limit; no partial stage was written')
    return result
