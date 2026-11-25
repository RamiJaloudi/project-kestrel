"""Physical reconstruction, never cosmetic masking or cloning Office/PDF objects."""
import io,json,subprocess,os,re,unicodedata
from pathlib import Path
from fastapi import HTTPException
from kestrel.adapters.extraction import canonical,digest
ROOT=Path(__file__).resolve().parents[3]
VERSION='flattened-text-pdf-v2'
CHECKS=['new_container_only','no_attachments','no_annotations_or_forms','no_images','no_actions','text_reconstruction','removed_text_absent','generic_metadata']
def compact(s):return ''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if not c.isspace())

def sanitize(source,spans):
    units=json.loads(source.units_json);by={u['number']:u for u in units};ranges={};manifest=[];removed=[]
    for s in sorted(spans,key=lambda x:(x['unit'],x['start'],x['end'])):
        u=by.get(s['unit'])
        if not u or not 0<=s['start']<s['end']<=len(u['text']):raise HTTPException(422,'Exact nonempty source range required')
        previous=ranges.setdefault(s['unit'],[])
        if previous and s['start']<previous[-1][1]:raise HTTPException(422,'Redaction ranges must not overlap')
        previous.append((s['start'],s['end']));quote=u['text'][s['start']:s['end']];removed.append(quote)
        manifest.append({**s,'quote_hash':digest(quote.encode()),'original_locator':u['locator']})
    from kestrel.adapters.workbook_safety import excluded,secrets
    omitted=excluded(source,units)
    removed.extend(secrets(source))
    output=[]
    for u in units:
        if u.get('hidden_content') or u.get('workbook_metadata') or u['number'] in omitted:
            removed.append(u['text']);continue
        text=u['text']
        for a,b in reversed(ranges.get(u['number'],[])):text=text[:a]+'[REDACTED]'+text[b:]
        output.append({'number':len(output)+1,'locator':'Sanitized section '+str(len(output)+1),'text':text})
    if not any(u['text'].replace('[REDACTED]','').strip() for u in output):raise HTTPException(422,'No substantive sanitized text remains')
    return output,manifest,removed


def render(title,units):
    from kestrel.adapters import runtime
    try:
        data=canonical({'title':title,'units':units}).encode()
        if len(data)>2*1024*1024:raise ValueError()
        content=runtime.run_bytes([runtime.python(),ROOT/'scripts/disclosure_pdf.py'],data=data,timeout=30,limit=3*1024*1024)
        if not content.startswith(b'%PDF-'):raise ValueError()
        return content
    except (OSError,ValueError,subprocess.TimeoutExpired):raise HTTPException(503,'Sanitized PDF renderer unavailable or exceeded bounds')


def validate(data,title,units,removed):
    from pypdf import PdfReader
    try:
        reader=PdfReader(io.BytesIO(data),strict=True);root=reader.trailer['/Root'];text=''.join(p.extract_text() or '' for p in reader.pages)
        if reader.is_encrypted or not 1<=len(reader.pages)<=150:raise ValueError()
        if any(k in root for k in ['/Names','/AcroForm','/OpenAction','/AA','/AF','/Metadata']):raise ValueError()
        if any(p.get('/Annots') or p.get('/AA') or p.get('/Resources',{}).get('/XObject') for p in reader.pages):raise ValueError()
        metadata=reader.metadata or {}
        if metadata.get('/Title')!='Sanitized disclosure' or metadata.get('/Author')!='Project Kestrel':raise ValueError()
        normalized=compact(text)
        if compact(title) not in normalized or any(compact(u['text']) not in normalized for u in units):raise ValueError()
        # Repeated removed material elsewhere must also be removed, rather than leaking through another unit/title.
        for secret in removed:
            if len(compact(secret))>=8 and compact(secret) in compact(text+title):raise ValueError()
        return {'passed':True,'checks':CHECKS,'pages':len(reader.pages),'renderer':VERSION,'validator':'rebuilt-pdf-structure-v1','bytes_hash':digest(data)}
    except Exception:raise HTTPException(422,'Sanitized output failed physical-content validation; review all occurrences and output text')
