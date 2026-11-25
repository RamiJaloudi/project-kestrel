"""Exact declared numeric normalization. No currency/unit/period inference or float arithmetic."""
import re
from decimal import Decimal,localcontext,InvalidOperation
from fastapi import HTTPException

def canonical_amount(value):
    with localcontext() as ctx:
        ctx.prec=64
        return '0' if value==0 else format(value.normalize(),'f')


def number(raw,decimal_mark,*,scientific=False):
    if decimal_mark not in {'.',','} or not isinstance(raw,str) or len(raw)>80:raise HTTPException(422,'Explicit decimal convention and bounded raw numeric token required')
    value=raw.strip().replace('\u00a0',' ').replace('\u202f',' ')
    if scientific:
        if not re.fullmatch(r'[+-]?[0-9]{1,38}(?:'+re.escape(decimal_mark)+r'[0-9]{1,12})?[eE][+-]?[0-9]{1,2}',value):raise HTTPException(422,'A bounded explicit scientific source token is required')
        return Decimal(value.replace(decimal_mark,'.'))
    negative=value.startswith('(') and value.endswith(')')
    if negative:value=value[1:-1].strip()
    if negative and value.startswith(('-','+')):raise HTTPException(422,'Ambiguous numeric sign')
    sign='-' if negative else '-' if value.startswith('-') else ''
    value=value.removeprefix('-').removeprefix('+')
    group=',' if decimal_mark=='.' else '.'
    parts=value.split(decimal_mark)
    if len(parts)>2 or (len(parts)==2 and not re.fullmatch(r'[0-9]{1,12}',parts[1])):raise HTTPException(422,'Invalid declared decimal token')
    integer=parts[0]
    if ' ' in integer and group in integer:raise HTTPException(422,'Mixed grouping separators')
    sep=' ' if ' ' in integer else group
    if sep in integer:
        chunks=integer.split(sep)
        if not re.fullmatch(r'[0-9]{1,3}',chunks[0]) or any(not re.fullmatch(r'[0-9]{3}',c) for c in chunks[1:]):raise HTTPException(422,'Invalid thousands grouping')
        integer=''.join(chunks)
    if not re.fullmatch(r'[0-9]{1,38}',integer):raise HTTPException(422,'A literal numeric source token is required')
    try:return Decimal(sign+integer+('.'+parts[1] if len(parts)==2 else ''))
    except InvalidOperation:raise HTTPException(422,'Invalid numeric evidence')


def base_amount(value,scale):
    if scale not in {'1','1000','1000000'}:raise HTTPException(422,'Explicit supported unit scale required')
    with localcontext() as ctx:
        ctx.prec=64;result=value*Decimal(scale)
        if not result.is_finite() or abs(result)>=Decimal('1e26') or result.as_tuple().exponent < -12:raise HTTPException(422,'Amount exceeds exact financial storage bounds')
        return result


def compare(left,right):
    with localcontext() as ctx:
        ctx.prec=64;a=Decimal(left);b=Decimal(right)
        return {'difference':canonical_amount(a-b),'percentage_change':None if not b else canonical_amount((a-b)/abs(b)*100)}
