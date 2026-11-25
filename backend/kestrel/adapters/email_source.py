"""Bounded inert MIME evidence and attachment staging, never auto-ingestion."""
import hashlib,re
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import PurePath

MAX_DECODED=3*1024*1024
ALLOWED={'.txt','.csv','.pdf','.docx','.xlsx','.xbrl','.xml','.ixbrl','.xhtml','.html','.htm'}

class Body(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.style=0;self.hidden=False
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag.lower() in {'script','iframe','object','embed','form'}:raise ValueError('Active HTML email body forbidden')
        if tag.lower()=='style':self.style+=1;self.hidden=True
        if 'hidden' in values or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden',values.get('style') or '',re.I):self.hidden=True
        if tag.lower() in {'p','div','br','li','tr'}:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag.lower()=='style':self.style=max(0,self.style-1)
    def handle_data(self,value):
        if not self.style:self.parts.append(value)

def safe_name(value):
    if not value or len(value)>160 or '/' in value or '\\' in value or any(ord(c)<32 or c=='\x7f' for c in value):raise ValueError('Unsafe MIME filename')
    if PurePath(value).suffix.lower() not in ALLOWED:raise ValueError('Attachment format needs an approved safe converter; executable, macro-enabled, archive and nested-email attachments are not staged')
    return value

def validate_attachment(name,data):
    if not data or len(data)>MAX_DECODED or data.startswith((b'MZ',b'\x7fELF',b'#!',b'\xd0\xcf\x11\xe0')):raise ValueError('Executable, binary or oversized attachment')
    from kestrel.adapters.extraction import extract
    parsed=extract(name,data)
    if name.lower().endswith('.pdf'):
        import io
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data),strict=True);root=reader.trailer['/Root'];names=root.get('/Names',{})
        if hasattr(names,'get_object'):names=names.get_object()
        if any(k in root for k in ['/OpenAction','/AA','/AcroForm','/AF','/Collection']) or any(k in names for k in ['/JavaScript','/EmbeddedFiles']) or any(p.get('/AA') or p.get('/Annots') or p.get('/AF') for p in reader.pages):raise ValueError('Active or attached PDF content is not staged')
    return parsed.get('sensitive_hidden',False)

def message(data):
    if len(data)>MAX_DECODED or any(len(line)>16384 for line in data.splitlines()):raise ValueError('Email bounds')
    mail=BytesParser(policy=policy.default.clone(raise_on_defect=True)).parsebytes(data)
    units=[];attachments=[];parts=0;decoded=0;text_size=0
    def add(locator,value,**metadata):
        nonlocal text_size
        text_size+=len(value)
        if text_size>150000:raise ValueError('Email text bound')
        units.append({'number':len(units)+1,'locator':locator,'text':value,**metadata})
    headers=[]
    for key,value in mail.items():
        if len(headers)>=100 or len(str(value))>4000:raise ValueError('Email header bound')
        headers.append(key+': '+str(value))
    add('Email headers','\n'.join(headers))
    def visit(part,depth):
        nonlocal parts,decoded
        parts+=1
        if parts>100 or depth>10 or len(part.keys())>100 or part.defects:raise ValueError('MIME structure bound or defect')
        filename=part.get_filename();disposition=part.get_content_disposition();kind=part.get_content_type()
        if kind in {'message/rfc822','message/partial','message/external-body'}:raise ValueError('Nested or external messages require a separate approved converter')
        if filename is not None or disposition=='attachment':
            name=safe_name(filename)
            if part.is_multipart() or len(attachments)>=25:raise ValueError('Attachment structure/count bound')
            value=part.get_payload(decode=True)
            if not isinstance(value,bytes):raise ValueError('Attachment decoding failed')
            decoded+=len(value)
            if decoded>MAX_DECODED:raise ValueError('Decoded email bound')
            validate_attachment(name,value)
            index=len(attachments)+1
            descriptor={'index':index,'file_name':name,'media_type':kind,'size':len(value),'bytes_hash':hashlib.sha256(value).hexdigest(),'state':'staged_not_ingested'}
            attachments.append({**descriptor,'data':value})
            add('Staged attachment '+str(index),'Attachment '+str(index)+': '+name+'\nDeclared MIME: '+kind+'\nBytes: '+str(len(value))+'\nSHA256: '+descriptor['bytes_hash']+'\nNot ingested. Explicit separate-source intake and classification required.',attachment=descriptor,hidden_content=True)
            return
        if part.is_multipart():
            for child in part.iter_parts():visit(child,depth+1)
            return
        if kind not in {'text/plain','text/html'}:raise ValueError('Unsupported inline MIME content; no automatic attachment conversion')
        value=part.get_payload(decode=True)
        if not isinstance(value,bytes):raise ValueError('MIME body decoding failed')
        decoded+=len(value)
        if decoded>MAX_DECODED:raise ValueError('Decoded email bound')
        charset=part.get_content_charset() or 'ascii'
        if charset.lower() not in {'utf-8','us-ascii','ascii','iso-8859-1','windows-1252'}:raise ValueError('Unsupported explicit email character set')
        value=value.decode(charset,errors='strict');hidden=False
        if kind=='text/html':
            parser=Body();parser.feed(value);parser.close();value=''.join(parser.parts);hidden=parser.hidden
        if value.strip():add('Email body '+str(parts),value,hidden_content=hidden)
    visit(mail,0)
    return units,attachments
