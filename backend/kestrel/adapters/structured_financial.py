"""Bounded evidence extraction, not a taxonomy validator or financial approval.

No schema, taxonomy, linkbase, script, URL or calculation is fetched/executed.
Numeric values use Decimal lexical arithmetic with explicit sign/scale only.
"""
import io,re
from datetime import date,datetime
from decimal import Decimal,localcontext
from defusedxml.ElementTree import iterparse

X='http://www.xbrl.org/2003/instance'
IX={'http://www.xbrl.org/2013/inlineXBRL','http://www.xbrl.org/2008/inlineXBRL'}
DIM='http://xbrl.org/2006/xbrldi'
REG='http://www.xbrl.org/inlineXBRL/transformation/2020-02-12'
XSI='{http://www.w3.org/2001/XMLSchema-instance}nil'
HTML='http://www.w3.org/1999/xhtml'

def split(tag):
    if tag.startswith('{'):return tuple(tag[1:].split('}',1))
    return '',tag

def qname(value,namespaces):
    if not value or len(value)>256:raise ValueError('QName bound')
    parts=value.split(':')
    if len(parts)>2 or any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*',p) for p in parts):raise ValueError('QName syntax')
    prefix,local=parts if len(parts)==2 else ('',parts[0])
    if prefix not in namespaces:raise ValueError('Unbound QName namespace')
    return '{'+namespaces[prefix]+'}'+local

def parse(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('DTD/entities forbidden')
    stack=[];pending=[];spaces={};parents={};count=0;ids={};root=None
    for event,item in iterparse(io.BytesIO(data),events=('start-ns','start','end'),forbid_dtd=True,forbid_entities=True,forbid_external=True):
        if event=='start-ns':pending.append(item);continue
        if event=='end':stack.pop();continue
        count+=1
        if count>10000 or len(stack)>32:raise ValueError('XML tree bound')
        ns=dict(spaces[id(stack[-1])]) if stack else {}
        ns.update(pending);pending=[];spaces[id(item)]=ns
        if stack:parents[id(item)]=stack[-1]
        else:root=item
        stack.append(item)
        ident=item.attrib.get('id')
        if ident:
            if ident in ids or len(ident)>128:raise ValueError('Duplicate or oversized XML ID')
            ids[ident]=item
        if any(len(str(v))>1000 for v in item.attrib.values()):raise ValueError('XML attribute bound')
    return root,spaces,parents,ids

def lexical_time(value):
    if not value or len(value)>40:raise ValueError('Context time required')
    try:
        if 'T' in value:datetime.fromisoformat(value.replace('Z','+00:00'))
        else:date.fromisoformat(value)
    except ValueError:raise ValueError('Unsupported context date/dateTime')
    return value

def text(element):return ''.join(element.itertext()).strip()

def decimal(value):
    if len(value)>100 or not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)',value):raise ValueError('Strict bounded decimal literal required')
    result=Decimal(value)
    if not result.is_finite() or len(result.as_tuple().digits)>80:raise ValueError('Decimal bound')
    return result

def number(element,raw,namespaces,inline):
    value=raw.strip();fmt=element.attrib.get('format')
    if fmt:
        expanded=qname(fmt,namespaces)
        if expanded not in {'{'+REG+'}num-dot-decimal','{'+REG+'}num-comma-decimal','{'+REG+'}fixed-zero'}:raise ValueError('Unsupported Inline XBRL numeric transformation')
        local=split(expanded)[1]
        if local=='fixed-zero':value='0'
        else:
            # Supported registry subset: decimal separator plus conventional
            # three-digit thousands groups; ambiguous/malformed groups reject.
            separator='.' if local=='num-dot-decimal' else ','
            grouping=',' if separator=='.' else '.'
            value=value.replace('\u00a0',' ').strip()
            if not re.fullmatch(r'(?:[0-9]+|[0-9]{1,3}(?:'+re.escape(grouping)+r'[0-9]{3})+)(?:'+re.escape(separator)+r'[0-9]+)?',value):raise ValueError('Unsupported formatted numeric lexical value')
            value=value.replace(grouping,'').replace(separator,'.')
    result=decimal(value)
    scale=element.attrib.get('scale','0');sign=element.attrib.get('sign')
    if not inline and (scale!='0' or sign is not None):raise ValueError('Inline-only sign/scale')
    if not re.fullmatch(r'-?[0-9]{1,2}',scale) or not -18<=int(scale)<=18:raise ValueError('Inline scale bound')
    if inline and (result<0 or sign not in {None,'-'}):raise ValueError('Inline sign requires nonnegative numeric content and explicit minus attribute')
    with localcontext() as ctx:
        ctx.prec=128
        result=result.scaleb(int(scale))
        if sign=='-':result=-result
    if len(format(result,'f'))>128:raise ValueError('Expanded decimal bound')
    return format(result,'f'),scale,sign,fmt

def extract_units(data):
    root,spaces,parents,ids=parse(data);namespace,local=split(root.tag)
    inline=namespace==HTML and local=='html'
    if not inline and (namespace,local)!=(X,'xbrl'):raise ValueError('XBRL instance or XML XHTML Inline XBRL document required')
    opaque_css=inline and any(split(e.tag)==(HTML,'style') or (split(e.tag)==(HTML,'link') and 'stylesheet' in e.attrib.get('rel','').lower()) for e in root.iter())
    contexts={};units={};result=[];total=0;has_hidden=False
    def add(locator,value,**metadata):
        nonlocal total
        total+=len(value)
        if total>150000 or len(result)>=1000:raise ValueError('Structured financial evidence bound')
        result.append({'number':len(result)+1,'locator':locator,'text':value,**metadata})
    for element in root.iter():
        ns,tag=split(element.tag)
        if not inline and element is not root and ns not in {X,'http://www.xbrl.org/2003/linkbase'}:
            parent=parents.get(id(element))
            if element.attrib.get('contextRef') is not None and parent is not root:raise ValueError('Nested facts require unsupported tuple mapping')
            if parent is root and element.attrib.get('contextRef') is None and len(element):raise ValueError('Unsupported XBRL tuple structure')
        if inline and ns in IX and tag in {'tuple','fraction','relationship'}:raise ValueError('Unsupported Inline XBRL tuple/fraction/relationship')
        if inline and ns==HTML and tag.lower() in {'script','iframe','object','embed'}:raise ValueError('Active XHTML content forbidden')
        if ns==X and tag=='context':
            cid=element.attrib.get('id');entity=element.find('{'+X+'}entity');period=element.find('{'+X+'}period')
            if not cid or entity is None or period is None or len(contexts)>=500:raise ValueError('Context structure or bound')
            identifiers=entity.findall('{'+X+'}identifier')
            if len(identifiers)!=1:raise ValueError('Unique entity identifier required')
            identifier=identifiers[0]
            dates={split(e.tag)[1]:text(e) for e in period}
            if set(dates)=={'instant'}:dates['instant']=lexical_time(dates['instant'])
            elif set(dates)=={'startDate','endDate'}:
                dates={k:lexical_time(v) for k,v in dates.items()}
                if dates['startDate']>dates['endDate']:raise ValueError('Reversed context period')
            elif set(dates)!={'forever'}:raise ValueError('Supported context period required')
            dimensions=[]
            for dim in element.iter():
                dn,dt=split(dim.tag)
                if dn!=DIM:continue
                dimension=qname(dim.attrib.get('dimension'),spaces[id(dim)])
                if dt=='explicitMember':dimensions.append({'dimension':dimension,'kind':'explicit','value':qname(text(dim),spaces[id(dim)])})
                elif dt=='typedMember':
                    if len(dim)!=1:raise ValueError('Typed dimension structure')
                    dimensions.append({'dimension':dimension,'kind':'typed','element':dim[0].tag,'value':text(dim[0])})
                else:raise ValueError('Unsupported dimension')
            context={'id':cid,'entity':text(identifier),'entity_scheme':identifier.attrib.get('scheme',''),'period':dates,'dimensions':dimensions,'raw_context_text':text(element)}
            if not context['entity'] or len(dimensions)>30:raise ValueError('Context entity/dimension bound')
            contexts[cid]=context
        elif ns==X and tag=='unit':
            uid=element.attrib.get('id')
            if not uid or len(units)>=100:raise ValueError('Unit bound')
            direct=element.findall('{'+X+'}measure');divide=element.find('{'+X+'}divide')
            if direct and divide is None:unit={'numerator':[qname(text(e),spaces[id(e)]) for e in direct],'denominator':[]}
            elif not direct and divide is not None:
                unit={key:[qname(text(e),spaces[id(e)]) for e in divide.findall('{'+X+'}'+name+'/{'+X+'}measure')] for key,name in [('numerator','unitNumerator'),('denominator','unitDenominator')]}
                if not unit['denominator']:raise ValueError('Unit denominator required')
            else:raise ValueError('Ambiguous unit structure')
            if not unit['numerator'] or len(unit['numerator'])+len(unit['denominator'])>10:raise ValueError('Unit measures bound')
            units[uid]=unit
    fact_count=0
    for element in root.iter():
        ns,tag=split(element.tag)
        is_inline=inline and ns in IX and tag in {'nonFraction','nonNumeric'}
        is_fact=not inline and element.attrib.get('contextRef') is not None and ns not in {X}
        if not is_inline and not is_fact:continue
        fact_count+=1
        if fact_count>500:raise ValueError('Fact count bound')
        if element.attrib.get('tupleRef') or element.attrib.get('target'):raise ValueError('Unsupported tuple or target document')
        context_ref=element.attrib.get('contextRef');unit_ref=element.attrib.get('unitRef')
        if context_ref not in contexts or (unit_ref and unit_ref not in units):raise ValueError('Dangling context/unit reference')
        concept=qname(element.attrib.get('name'),spaces[id(element)]) if inline else element.tag
        nil=element.attrib.get(XSI,'false')
        if nil not in {'false','0','true','1'}:raise ValueError('Invalid nil attribute')
        nil=nil in {'true','1'};raw=text(element);continuation=element.attrib.get('continuedAt');visited=set()
        while continuation:
            if continuation in visited or len(visited)>=20:raise ValueError('Continuation cycle or bound')
            visited.add(continuation);other=ids.get(continuation)
            if other is None or split(other.tag)[0] not in IX or split(other.tag)[1]!='continuation':raise ValueError('Continuation unavailable')
            raw+=text(other);continuation=other.attrib.get('continuedAt')
        if inline and any(split(e.tag)[0] in IX and split(e.tag)[1]=='exclude' for e in element.iter()):raise ValueError('Inline exclude requires unsupported lexical mapping')
        numeric=(tag=='nonFraction') if inline else bool(unit_ref)
        if numeric and not inline and len(element):raise ValueError('Fraction/structured numeric items require unsupported typed mapping')
        decimals=element.attrib.get('decimals');precision=element.attrib.get('precision')
        if numeric and not unit_ref:raise ValueError('Numeric unit required')
        if decimals is not None and precision is not None:raise ValueError('Decimals and precision are mutually exclusive')
        if numeric and not nil and decimals is None and precision is None:raise ValueError('Numeric accuracy declaration required')
        if nil and (raw or decimals is not None or precision is not None):raise ValueError('Nil facts have no value or accuracy declaration')
        if decimals is not None and not re.fullmatch(r'INF|-?[0-9]{1,3}',decimals):raise ValueError('Decimals declaration')
        if precision is not None and not re.fullmatch(r'INF|[1-9][0-9]{0,2}',precision):raise ValueError('Precision declaration')
        # CSS is never evaluated. A stylesheet makes visibility uncertain, so
        # every fact retains the conservative hidden-content restriction.
        ancestor=element;hidden=opaque_css
        while ancestor is not None:
            an,at=split(ancestor.tag)
            hidden=hidden or (an in IX and at=='hidden') or ancestor.attrib.get('hidden') is not None or bool(re.search(r'(display\s*:\s*none|visibility\s*:\s*hidden)',ancestor.attrib.get('style',''),re.I))
            ancestor=parents.get(id(ancestor))
        has_hidden=has_hidden or hidden
        value,scale,sign,fmt=(None,'0',None,None) if nil or not numeric else number(element,raw,spaces[id(element)],inline)
        context=contexts[context_ref];unit=units.get(unit_ref)
        evidence={'kind':'ixbrl' if inline else 'xbrl','fact_index':fact_count,'fact_id':element.attrib.get('id'),'concept':concept,'context':context,'unit_id':unit_ref,'unit':unit,
            'numeric':numeric,'nil':nil,'raw_value':raw,'decimal_value':value,'decimals':decimals,'precision':precision,'scale':scale,'sign':sign,'format':fmt,'hidden':hidden,'css_visibility_unresolved':opaque_css}
        import json
        rendered='Concept: '+concept+'\nContext: '+json.dumps(context,sort_keys=True,ensure_ascii=False)+'\nUnit: '+json.dumps(unit,sort_keys=True,ensure_ascii=False)+'\nRaw value: '+raw+'\nDecimal value: '+(value if value is not None else 'NIL (no value)' if nil else 'Non-numeric')+'\nAccuracy: decimals='+str(decimals)+'; precision='+str(precision)+'; scale='+scale+'; sign='+str(sign)
        add(('Inline XBRL' if inline else 'XBRL')+' fact '+str(fact_count),rendered,structured_financial=evidence,hidden_content=hidden)
    if not fact_count:raise ValueError('No supported XBRL facts')
    return result,has_hidden
