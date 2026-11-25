"""Bounded literal workbook XML/CSV evidence. Never evaluates a formula or cached result."""
import csv
import io
import posixpath
import re
import zipfile
import hashlib
import json
from defusedxml.ElementTree import fromstring

NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
SAFETY_VERSION='literal-workbook-safety-1'

def package_relationships(z):
    """Resolve local targets only; retain opaque relationship hashes, never run them."""
    known={'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'+name for name in ['officeDocument','worksheet','styles','sharedStrings','theme','extended-properties']}
    known.add('http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties')
    retained=[];members=set(z.namelist())
    for path in sorted(name for name in members if name.endswith('.rels')):
        root=fromstring(z.read(path));seen=set()
        folder=path.split('/_rels/',1)[0] if '/_rels/' in path else ''
        for rel in root:
            rid=rel.attrib.get('Id','');target=rel.attrib.get('Target','');kind=rel.attrib.get('Type','')
            if not rid or rid in seen or len(target)>240 or any(ord(c)<32 for c in target) or '\\' in target or ':' in target or rel.attrib.get('TargetMode','Internal').casefold()!='internal':raise ValueError('Unsafe workbook relationship')
            seen.add(rid)
            resolved=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(folder,target))
            if resolved.startswith('../') or resolved not in members or resolved.endswith('/'):raise ValueError('Unresolved workbook relationship')
            if kind not in known:
                retained.append('Opaque relationship '+path+' #'+rid+' type='+kind+' target='+resolved+'; SHA256='+hashlib.sha256(z.read(resolved)).hexdigest())
    return retained


def formula_ast(value):
    if not isinstance(value,str) or len(value)>2048:raise ValueError('Formula bound')
    pattern=re.compile(r'\s*(\$?[A-Za-z]{1,3}\$?[1-9][0-9]*|[A-Za-z_][A-Za-z_0-9.]*|(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?|[()+*/^,:-])')
    tokens=[];offset=0
    while offset<len(value):
        m=pattern.match(value,offset)
        if not m:raise ValueError('Unsupported formula token')
        tokens.append(m[1]);offset=m.end()
        if len(tokens)>256:raise ValueError('Formula token bound')
    index=0
    def expr(minimum=0,depth=0):
        nonlocal index
        if depth>32 or index>=len(tokens):raise ValueError('Formula nesting or syntax')
        t=tokens[index];index+=1
        if t in {'+','-'}:left={'kind':'unary','operator':t,'value':expr(40,depth+1)}
        elif t=='(':
            left=expr(0,depth+1)
            if index>=len(tokens) or tokens[index]!=')':raise ValueError('Missing parenthesis')
            index+=1
        elif re.fullmatch(r'\$?[A-Za-z]{1,3}\$?[1-9][0-9]*',t):left={'kind':'cell','reference':t.upper()}
        elif re.fullmatch(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',t):left={'kind':'number','literal':t}
        elif t.upper() in {'SUM','AVERAGE','MIN','MAX'}:
            if index>=len(tokens) or tokens[index]!='(':raise ValueError('Function parentheses')
            index+=1;args=[expr(0,depth+1)]
            while index<len(tokens) and tokens[index]==',':
                index+=1;args.append(expr(0,depth+1))
                if len(args)>32:raise ValueError('Argument bound')
            if index>=len(tokens) or tokens[index]!=')':raise ValueError('Function syntax')
            index+=1;left={'kind':'function','name':t.upper(),'arguments':args}
        else:raise ValueError('Unsupported function or reference')
        while index<len(tokens) and tokens[index] in {'+','-','*','/','^',':'}:
            op=tokens[index];prec={'+':10,'-':10,'*':20,'/':20,'^':30,':':50}[op]
            if prec<minimum:break
            index+=1;right=expr(prec if op=='^' else prec+1,depth+1)
            if op==':' and (left['kind']!='cell' or right['kind']!='cell'):raise ValueError('Range endpoints')
            left={'kind':'range' if op==':' else 'binary','operator':op,'left':left,'right':right}
        return left
    result=expr()
    if index!=len(tokens):raise ValueError('Trailing formula syntax')
    return result


def column(reference):
    m=re.fullmatch(r'([A-Z]+)([1-9][0-9]*)',reference)
    if not m:raise ValueError('Cell coordinate')
    value=0
    for c in m[1]:value=value*26+ord(c)-64
    row=int(m[2])
    if value>50 or row>1000:raise ValueError('Cell bound')
    return value,row


def units_from_rows(rows):
    result=[];total=0;count=0
    for sheet,state,row_number,cells in rows:
        fragments=[];offset=0
        for cell in cells:
            count+=1
            if count>5000:raise ValueError('Cell count bound')
            value=cell['raw_value']
            if cell.get('formula') is not None:
                value='Formula ='+cell['formula']+'; cached (unverified): '+(cell['cached_value'] if cell['cached_value'] is not None else 'UNKNOWN')
            prefix=cell['coordinate']+': ';start=offset+len(prefix);fragment=prefix+value
            cell.update({'text':value,'start':start,'end':start+len(value)})
            fragments.append(fragment);offset+=len(fragment)+3
        text=' | '.join(fragments);total+=len(text)
        if total>150000:raise ValueError('Extracted text bound')
        if text:result.append({'number':len(result)+1,'locator':f'{sheet}, row {row_number}' if sheet!='CSV' else f'CSV row {row_number}','text':text,'sheet':sheet,'sheet_state':state,'row':row_number,'cells':cells})
    return result


def workbook(data,*,extended=False):
    # Caller applies office_guard first, including ZIP/XML/relationship limits.
    rows=[]
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        book=fromstring(z.read('xl/workbook.xml'));rels=fromstring(z.read('xl/_rels/workbook.xml.rels'))
        targets={r.attrib['Id']:r.attrib['Target'] for r in rels}
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(t.text or '' for t in si.iter(NS+'t')) for si in fromstring(z.read('xl/sharedStrings.xml'))]
            if len(shared)>5000 or sum(map(len,shared))>150000:raise ValueError('Shared strings bound')
        names=set();cell_count=0;sheet_manifest=[]
        for sheet in book.find(NS+'sheets'):
            name=sheet.attrib['name'];state=sheet.attrib.get('state','visible')
            if not 1<=len(name)<=31 or any(ord(c)<32 for c in name):raise ValueError('Worksheet name bound')
            if name.casefold() in names or state not in {'visible','hidden','veryHidden'}:raise ValueError('Ambiguous sheet')
            names.add(name.casefold())
            entry={'name':name,'state':state,'hidden_rows':[],'hidden_columns':[]};sheet_manifest.append(entry)
            if len(names)>50:raise ValueError('Worksheet count bound')
            target=targets[sheet.attrib[REL]]
            path=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl',target))
            if not path.startswith('xl/worksheets/') or '..' in path.split('/'):raise ValueError('Worksheet relationship')
            root=fromstring(z.read(path));seen=set();seen_rows=set();hidden_columns=set()
            if extended:
                for col in root.iter(NS+'col'):
                    if col.attrib.get('hidden') not in {None,'0','1','false','true'}:raise ValueError('Ambiguous hidden column state')
                    if col.attrib.get('hidden') not in {'1','true'}:continue
                    first=int(col.attrib['min']);last=int(col.attrib['max'])
                    if not 1<=first<=last<=16384:raise ValueError('Hidden column range')
                    entry['hidden_columns'].append([first,last])
                    if len(entry['hidden_columns'])>1000:raise ValueError('Hidden column definition bound')
                    hidden_columns.update(range(first,min(last,50)+1))
            for row in root.iter(NS+'row'):
                if extended and row.attrib.get('hidden') not in {None,'0','1','false','true'}:raise ValueError('Ambiguous hidden row state')
                row_no=int(row.attrib['r'])
                if not 1<=row_no<=1000 or row_no in seen_rows:raise ValueError('Row bound or duplicate row')
                seen_rows.add(row_no)
                if extended and row.attrib.get('hidden') in {'1','true'}:entry['hidden_rows'].append(row_no)
                cells=[]
                for c in row.findall(NS+'c'):
                    if len(c.attrib)>20 or any(len(v)>256 for v in c.attrib.values()):raise ValueError('Cell attribute bound')
                    cell_count+=1
                    if cell_count>5000:raise ValueError('Cell count bound')
                    coord=c.attrib['r'];col,rn=column(coord)
                    if rn!=row_no or coord in seen:raise ValueError('Duplicate or misplaced cell')
                    seen.add(coord);kind=c.attrib.get('t','n');v=c.find(NS+'v');raw=v.text if v is not None and v.text is not None else ''
                    if kind=='s':
                        if not re.fullmatch(r'[0-9]+',raw) or int(raw)>=len(shared):raise ValueError('Shared string reference')
                        raw=shared[int(raw)]
                    elif kind=='inlineStr':raw=''.join(t.text or '' for t in c.iter(NS+'t'))
                    f=c.find(NS+'f')
                    if f is None and raw=='':continue
                    cell={'coordinate':coord,'column':col,'raw_value':raw,'value_kind':kind,'style_id':c.attrib.get('s'),'formula':None,'cached_value':None}
                    if extended:cell['hidden']=state!='visible' or row.attrib.get('hidden') in {'1','true'} or col in hidden_columns
                    if f is not None:
                        if len(f.attrib)>20 or any(len(v)>256 for v in f.attrib.values()):raise ValueError('Formula attribute bound')
                        formula=f.text or '';cell.update({'formula':formula,'cached_value':raw or None,'formula_attributes':dict(f.attrib),'formula_ast':None,'formula_error':None})
                        try:cell['formula_ast']=formula_ast(formula)
                        except ValueError:cell['formula_error']='Unsupported or bounded formula; not evaluated'
                    cells.append(cell)
                if cells:rows.append((name,state,row_no,cells))
        retained=[];private_literals=[]
        if extended:
            retained.extend(package_relationships(z))
            for element in book.iter(NS+'definedName'):
                retained.append('Defined name '+element.attrib.get('name','')+' (hidden='+element.attrib.get('hidden','0')+'): '+(element.text or ''))
                value=element.text or '';private_literals.extend([element.attrib.get('name',''),value])
                if value.startswith('"') and value.endswith('"'):private_literals.append(value[1:-1].replace('""','"'))
            for path in sorted(z.namelist()):
                if ('comment' in path.lower() or 'person' in path.lower()) and path.endswith('.xml'):
                    element=fromstring(z.read(path));values=[value for node in element.iter() for value in [*(node.attrib.values()),node.text or ''] if value.strip()]
                    retained.append(path+': '+json.dumps(values,ensure_ascii=True));private_literals.extend(values)
                elif any(part in path.lower() for part in ['vbaproject','xl/embeddings/','xl/activex/','customui/']):
                    retained.append('Opaque active content retained but never executed or converted: '+path+'; SHA256='+hashlib.sha256(z.read(path)).hexdigest())
    result=units_from_rows(rows)
    if extended:
        for unit in result:unit['hidden_content']=any(c.get('hidden') for c in unit['cells'])
        protected=bool(retained) or any(s['state']!='visible' or s['hidden_rows'] or s['hidden_columns'] for s in sheet_manifest)
        formula_rows=[(u['sheet'],u['row']) for u in result if any(c.get('formula') is not None for c in u['cells'])]
        private_literals=sorted(set(value for value in private_literals if value))
        if sum(map(len,private_literals))>150000:raise ValueError('Private workbook metadata bound')
        descriptor={'sheets':sheet_manifest,'metadata':retained,'formula_rows':formula_rows,'private_literals':private_literals}
        safety={'schema':SAFETY_VERSION,'bytes_hash':hashlib.sha256(data).hexdigest(),'visibility_hash':hashlib.sha256(json.dumps(descriptor,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest(),'sensitive_hidden':protected,'has_formulas':bool(formula_rows)}
        manifest='\n'.join('Worksheet '+item['name']+': '+item['state']+'; hidden rows='+str(item['hidden_rows'])+'; hidden columns='+str(item['hidden_columns']) for item in sheet_manifest)
        result.append({'number':len(result)+1,'locator':'Workbook worksheet manifest','text':manifest,'workbook_sheets':sheet_manifest,'workbook_metadata':True,'hidden_content':protected})
        if result:result[0]['workbook_sheets']=sheet_manifest
        if retained:
            value='\n'.join(retained)
            if len(value)+sum(len(u['text']) for u in result)>150000:raise ValueError('Retained workbook metadata bound')
            result.append({'number':len(result)+1,'locator':'Workbook retained hidden and opaque metadata','text':value,'protected_literals':private_literals,'workbook_metadata':True,'hidden_content':True})
        result[0]['workbook_safety']=safety
    return result


def csv_units(data):
    rows=[]
    for r,values in enumerate(csv.reader(io.StringIO(data.decode('utf-8-sig')),strict=True),1):
        if r>1000 or len(values)>50:raise ValueError('CSV bounds')
        cells=[]
        for i,value in enumerate(values,1):
            name='';n=i
            while n:name=chr(65+(n-1)%26)+name;n=(n-1)//26
            cells.append({'coordinate':name+str(r),'column':i,'raw_value':value,'value_kind':'literal','formula':None,'cached_value':None})
        if cells:rows.append(('CSV','visible',r,cells))
    return units_from_rows(rows)
