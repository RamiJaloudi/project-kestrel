"""Bounded digital-text extraction. Never executes Office formulas or macros."""
import hashlib
import io
import json
from pathlib import PurePath
import re
import zipfile
from fastapi import HTTPException

MAX_BYTES=3*1024*1024
MAX_TEXT=150000

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def digest(value):return hashlib.sha256(value).hexdigest()

def office_guard(data,required,*,allow_inert_macros=False):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            files=archive.infolist()
            if len(files)>1000 or len({i.filename for i in files})!=len(files) or sum(i.file_size for i in files)>30*1024*1024:raise ValueError()
            if required not in archive.namelist():raise ValueError()
            for entry in files:
                name=entry.filename.lower()
                if len(name)>240 or name.startswith('/') or '\\' in name or '..' in name.split('/'):raise ValueError()
                active=any(marker in name for marker in ['vbaproject','/activex/','/embeddings/','customui/'])
                if (active and not allow_inert_macros) or 'externallinks/' in name or entry.flag_bits&1:raise ValueError()
                if name.endswith(('.xml','.rels')):
                    raw=archive.read(entry)
                    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError()
                    # External references are not used by extraction, and are rejected on upload.
                    if name.endswith('.rels') and re.search(br'TargetMode\s*=\s*[\x22\x27]External',raw,re.I):raise ValueError()
                    if name.endswith('.rels'):
                        from defusedxml.ElementTree import fromstring
                        if any(r.attrib.get('TargetMode','').strip().casefold()=='external' for r in fromstring(raw)):raise ValueError()
    except Exception:raise HTTPException(422,'Unsupported or unsafe Office package')

def extract(name,data):
    if not data or len(data)>MAX_BYTES:raise HTTPException(413,'A nonempty file of at most 3 MiB is required')
    if len(name)>160 or '/' in name or '\\' in name or any(ord(c)<32 for c in name):raise HTTPException(422,'A plain file name is required')
    ext=PurePath(name).suffix.lower();units=[]
    def add(locator,text):
        text=text.replace('\r\n','\n').replace('\r','\n')
        if sum(len(u['text']) for u in units)+len(text)>MAX_TEXT:raise HTTPException(413,'Extracted text limit exceeded')
        units.append({'number':len(units)+1,'locator':locator,'text':text})
    try:
        if ext=='.pdf':
            from pypdf import PdfReader,__version__
            if not data.startswith(b'%PDF-'):raise ValueError()
            reader=PdfReader(io.BytesIO(data),strict=True)
            if reader.is_encrypted or len(reader.pages)>50:raise ValueError()
            for index,page in enumerate(reader.pages):add(f'Page {index+1}',page.extract_text() or '')
            media='application/pdf';engine='pypdf-'+__version__
        elif ext=='.docx':
            from docx import Document,__version__
            office_guard(data,'word/document.xml')
            doc=Document(io.BytesIO(data))
            for index,paragraph in enumerate(doc.paragraphs):
                if paragraph.text:add(f'Paragraph {index+1}',paragraph.text)
            for t,table in enumerate(doc.tables):
                for r,row in enumerate(table.rows):add(f'Table {t+1}, row {r+1}',' | '.join(c.text for c in row.cells))
            media='application/vnd.openxmlformats-officedocument.wordprocessingml.document';engine='python-docx-'+__version__
        elif ext in {'.xlsx','.xlsm'}:
            from kestrel.adapters.spreadsheet_source import workbook
            office_guard(data,'xl/workbook.xml',allow_inert_macros=ext=='.xlsm');units=workbook(data,extended=True)
            media='application/vnd.ms-excel.sheet.macroEnabled.12' if ext=='.xlsm' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';engine='literal-xlsm-inert-2' if ext=='.xlsm' else 'literal-workbook-xml-3'
        elif ext in {'.xbrl','.xml','.ixbrl','.xhtml','.html','.htm'}:
            from kestrel.adapters.structured_financial import extract_units
            units,_=extract_units(data);media='application/xml';engine='bounded-xbrl-decimal-1'
        elif ext=='.eml':
            from kestrel.adapters.email_source import message
            units,_=message(data);media='message/rfc822';engine='bounded-email-staging-1'
        elif ext=='.csv':
            from kestrel.adapters.spreadsheet_source import csv_units
            units=csv_units(data);media='text/csv';engine='literal-csv-2'
        elif ext=='.txt':
            add('Text 1',data.decode('utf-8-sig'));media='text/plain';engine='utf8-1'
        else:raise HTTPException(415,'Supported: PDF, DOCX, XLSX, inert XLSM, XBRL/XML iXBRL, EML, UTF-8 TXT and CSV; legacy XLS, MSG, PST and OST require an approved safe converter')
    except HTTPException:raise
    except Exception:raise HTTPException(422,'Document could not be safely extracted')
    if sum(len(u['text']) for u in units)>MAX_TEXT:raise HTTPException(413,'Extracted text limit exceeded')
    status='ready' if units and all(u['text'].strip() for u in units) else 'ocr_required'
    if not any(u['text'].strip() for u in units):status='ocr_required'
    return {'units':units,'media_type':media,'extractor':engine,'status':status,'sensitive_hidden':any(u.get('hidden_content') for u in units),
            'bytes_hash':digest(data),'text_hash':digest(canonical(units).encode())}
