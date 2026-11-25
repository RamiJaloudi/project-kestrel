"""Synthetic bounded adapters; no macros, taxonomy/network fetch or auto intake."""
import io,json,zipfile,hashlib
from email.message import EmailMessage
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from test_auth_policy import env,login
from test_observability_governance import post
from test_document_workflow import BASE
from kestrel.adapters.extraction import extract,canonical

def xlsm(*,external=False):
 from test_financial_source_cells import workbook
 out=io.BytesIO()
 with zipfile.ZipFile(io.BytesIO(workbook())) as src,zipfile.ZipFile(out,'w') as target:
  for item in src.infolist():
   data=src.read(item.filename)
   if item.filename=='xl/worksheets/sheet1.xml':data=data.replace(b'<row r="2">',b'<row r="2" hidden="1">')
   if item.filename=='xl/workbook.xml':data=data.replace(b'<definedNames/>',b'<definedNames><definedName name="PrivateNamedFormula" hidden="1">"NAMED_SECRET_813"</definedName></definedNames>')
   if external and item.filename=='xl/_rels/workbook.xml.rels':
    mode=b'Ex&#116;ernal' if external=='encoded' else b'External'
    data=data.replace(b'</Relationships>',b'<Relationship Id="rBad" Type="external" Target="https://example.invalid/private" TargetMode="'+mode+b'"/></Relationships>')
   target.writestr(item,data)
  target.writestr('xl/vbaProject.bin',b'MZ-SYNTHETIC_MACRO_NEVER_EXECUTE_772')
  target.writestr('xl/comments/comment99.xml',b'<comments xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><commentList><comment ref="A1"><text><t>COMMENT_SECRET_914</t></text></comment></commentList></comments>')
 return out.getvalue()

CONTEXT='''<x:context id="FY"><x:entity><x:identifier scheme="urn:synthetic:entity">Vireo</x:identifier><x:segment><d:explicitMember dimension="s:RegionAxis">s:Europe</d:explicitMember></x:segment></x:entity><x:period><x:startDate>2025-01-01</x:startDate><x:endDate>2025-12-31</x:endDate></x:period></x:context><x:unit id="EUR"><x:measure>iso:EUR</x:measure></x:unit>'''
NS='xmlns:x="http://www.xbrl.org/2003/instance" xmlns:s="urn:synthetic:concept" xmlns:iso="http://www.xbrl.org/2003/iso4217" xmlns:d="http://xbrl.org/2006/xbrldi" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
def xbrl(facts=None):
 return ('<x:xbrl '+NS+'>'+CONTEXT+(facts or '<s:Revenue id="revenue" contextRef="FY" unitRef="EUR" decimals="3">9007199254740993.125</s:Revenue><s:Loss contextRef="FY" unitRef="EUR" decimals="3">-0.125</s:Loss>')+'</x:xbrl>').encode()
def ixbrl(*,fmt='ixt:num-comma-decimal',hidden=True):
 fact='<ix:nonFraction id="revenue" name="s:Revenue" contextRef="FY" unitRef="EUR" decimals="3" scale="3" sign="-" format="'+fmt+'">9.007.199.254.740.993,125</ix:nonFraction>'
 return ('<html xmlns="http://www.w3.org/1999/xhtml" '+NS+' xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"><head><title>Synthetic filing</title></head><body><ix:header><ix:resources>'+CONTEXT+'</ix:resources>'+(('<ix:hidden>'+fact+'</ix:hidden>') if hidden else '')+'</ix:header>'+('' if hidden else fact)+'</body></html>').encode()
def eml(name='evidence.csv',attachment=b'entity,amount\nVireo,9007199254740993.125\n'):
 mail=EmailMessage();mail['Subject']='Synthetic finance evidence';mail['From']='seller@example.invalid';mail['To']='lawyer@example.invalid';mail.set_content('Synthetic financial email body, not a legal approval.')
 if name:mail.add_attachment(attachment,maintype='application',subtype='octet-stream',filename=name)
 return mail.as_bytes()

def test_xlsm_literal_tokens_hidden_rows_and_opaque_metadata_never_execute():
 from kestrel.adapters.document_reader import presentation
 from kestrel.adapters.disclosure import sanitize
 data=xlsm();value=extract('synthetic.xlsm',data);units=value['units'];assert value['sensitive_hidden']
 row=next(u for u in units if u['locator']=='Visible, row 2');assert row['hidden_content']
 cell=next(c for c in row['cells'] if c['coordinate']=='C2');assert cell['raw_value']=='9007199254740993.125'
 assert row['text'][cell['start']:cell['end']]=='9007199254740993.125'
 metadata=next(u for u in units if u['locator'].startswith('Workbook retained'))
 assert 'NAMED_SECRET_813' in metadata['text'] and 'COMMENT_SECRET_914' in metadata['text']
 assert 'SYNTHETIC_MACRO_NEVER_EXECUTE_772' not in canonical(units) and hashlib.sha256(b'MZ-SYNTHETIC_MACRO_NEVER_EXECUTE_772').hexdigest() in metadata['text']
 source=SimpleNamespace(file_name='synthetic.xlsm',data=data,units_json=canonical(units))
 reader=presentation(source);assert reader['format']=='excel' and reader['sheets'][1]['state']=='veryHidden'
 safe,_,removed=sanitize(source,[{'unit':1,'start':0,'end':2}]);rendered=canonical(safe)
 for private in ['NAMED_SECRET_813','COMMENT_SECRET_914','SYNTHETIC_HIDDEN_881','9007199254740993.125']:assert private not in rendered
 assert data==source.data
 with pytest.raises(HTTPException):extract('synthetic.xlsx',data)
 with pytest.raises(HTTPException):extract('synthetic.xlsm',xlsm(external=True))
 with pytest.raises(HTTPException):extract('synthetic.xlsm',xlsm(external='encoded'))

def test_xbrl_exact_decimal_context_dimension_units_and_nil_evidence():
 value=extract('synthetic.xbrl',xbrl());fact=value['units'][0]['structured_financial']
 assert fact['decimal_value']=='9007199254740993.125' and fact['raw_value']==fact['decimal_value']
 assert fact['context']['entity']=='Vireo' and fact['context']['period']['endDate']=='2025-12-31'
 assert fact['context']['dimensions'][0]['value']=='{urn:synthetic:concept}Europe'
 assert fact['unit']['numerator']==['{http://www.xbrl.org/2003/iso4217}EUR']
 assert value['units'][1]['structured_financial']['decimal_value']=='-0.125' and not value['sensitive_hidden']
 nil=extract('synthetic.xml',xbrl('<s:Revenue contextRef="FY" unitRef="EUR" xsi:nil="true"/>'))['units'][0]['structured_financial']
 assert nil['nil'] and nil['decimal_value'] is None and 'NIL (no value)' in extract('synthetic.xml',xbrl('<s:Revenue contextRef="FY" unitRef="EUR" xsi:nil="true"/>'))['units'][0]['text']

def test_ixbrl_explicit_numeric_transform_scale_sign_and_hidden_evidence():
 from kestrel.adapters.document_reader import presentation
 value=extract('synthetic.xhtml',ixbrl());fact=value['units'][0]['structured_financial']
 assert fact['decimal_value']=='-9007199254740993125' and fact['scale']=='3' and fact['sign']=='-'
 assert fact['raw_value']=='9.007.199.254.740.993,125' and fact['hidden'] and value['sensitive_hidden']
 reader=presentation(SimpleNamespace(file_name='synthetic.xhtml',units_json=canonical(value['units']),data=ixbrl()))
 assert reader['format']=='text' and reader['blocks'] and '<iframe' not in canonical(reader)
 with pytest.raises(HTTPException):extract('synthetic.xhtml',ixbrl(fmt='ixt:unreviewed-transform'))
 with pytest.raises(HTTPException):extract('synthetic.html',b'<html><body>Not XML Inline XBRL</body></html>')
 css=ixbrl(hidden=False).replace(b'<head>',b'<head><style>.private {display:none}</style>')
 parsed=extract('style.xhtml',css)
 assert parsed['sensitive_hidden'] and parsed['units'][0]['structured_financial']['css_visibility_unresolved']

def test_xbrl_divided_units_are_retained_without_inventing_a_currency_or_rate():
 unit=b'<x:unit id="EUR"><x:divide><x:unitNumerator><x:measure>iso:EUR</x:measure></x:unitNumerator><x:unitDenominator><x:measure>x:shares</x:measure></x:unitDenominator></x:divide></x:unit>'
 data=xbrl().replace(b'<x:unit id="EUR"><x:measure>iso:EUR</x:measure></x:unit>',unit)
 fact=extract('ratio.xbrl',data)['units'][0]['structured_financial']
 assert fact['unit']['denominator']==['{http://www.xbrl.org/2003/instance}shares']
 assert fact['decimal_value']=='9007199254740993.125'

def test_xbrl_fraction_and_tuple_structure_cannot_be_flattened_into_false_numbers():
 fraction='<s:Ownership contextRef="FY" unitRef="EUR"><x:numerator>1</x:numerator><x:denominator>2</x:denominator></s:Ownership>'
 with pytest.raises(HTTPException):extract('fraction.xbrl',xbrl(fraction))
 nested='<s:Tuple><s:Revenue contextRef="FY" unitRef="EUR" decimals="0">12</s:Revenue></s:Tuple>'
 with pytest.raises(HTTPException):extract('tuple.xbrl',xbrl(nested))

def test_structured_tree_and_email_attachment_counts_have_hard_bounds():
 deep=b'<x:xbrl '+NS.encode()+b'>'+b'<s:n>'*40+b'</s:n>'*40+b'</x:xbrl>'
 with pytest.raises(HTTPException):extract('deep.xbrl',deep)
 mail=EmailMessage();mail['Subject']='Bounded attachments';mail.set_content('Synthetic body')
 for i in range(26):mail.add_attachment(b'a,b\n1,2\n',maintype='application',subtype='octet-stream',filename=str(i)+'.csv')
 with pytest.raises(HTTPException):extract('many.eml',mail.as_bytes())

@pytest.mark.parametrize('data',[
 b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///C:/private">]><x/>',
 xbrl().replace(b'id="FY"',b'id="EUR"'),
 xbrl().replace(b'contextRef="FY"',b'contextRef="missing"'),
 xbrl().replace(b'iso:EUR',b'notbound:EUR'),
 xbrl().replace(b'9007199254740993.125',b'NaN'),
 xbrl().replace(b'decimals="3"',b'decimals="3" precision="10"'),
 ixbrl().replace(b'<body>',b'<body><script>fetch("https://example.invalid")</script>'),
])
def test_structured_xml_ambiguity_entities_active_content_and_nonfinite_values_denied(data):
 with pytest.raises(HTTPException) as error:extract('synthetic.xml',data)
 assert error.value.status_code==422

def test_email_body_and_staging_manifest_are_inert_and_do_not_ingest_attachment_text():
 from kestrel.adapters.email_source import message
 data=eml();value=extract('synthetic.eml',data);units,attachments=message(data)
 assert value['sensitive_hidden'] and len(attachments)==1
 assert attachments[0]['data']==b'entity,amount\nVireo,9007199254740993.125\n'
 assert '9007199254740993.125' not in canonical(units)
 assert units[-1]['attachment']['bytes_hash']==hashlib.sha256(attachments[0]['data']).hexdigest()
 assert units[-1]['attachment']['state']=='staged_not_ingested'
 assert not extract('body-only.eml',eml(None))['sensitive_hidden']

def test_email_pdf_active_actions_and_office_embedded_objects_are_rejected():
 from pypdf import PdfWriter
 from pypdf.generic import NameObject,DictionaryObject,TextStringObject
 writer=PdfWriter();writer.add_blank_page(width=200,height=200);plain=io.BytesIO();writer.write(plain)
 assert extract('plain-pdf.eml',eml('source.pdf',plain.getvalue()))['sensitive_hidden']
 writer._root_object[NameObject('/OpenAction')]=DictionaryObject({NameObject('/S'):NameObject('/JavaScript'),NameObject('/JS'):TextStringObject('SYNTHETIC_SCRIPT_NOT_EXECUTED')})
 active=io.BytesIO();writer.write(active)
 with pytest.raises(HTTPException):extract('active-pdf.eml',eml('source.pdf',active.getvalue()))
 from test_financial_source_cells import workbook
 out=io.BytesIO()
 with zipfile.ZipFile(io.BytesIO(workbook())) as source,zipfile.ZipFile(out,'w') as target:
  for item in source.infolist():target.writestr(item,source.read(item.filename))
  target.writestr('xl/embeddings/oleObject1.bin',b'MZ-OPAQUE_EXECUTABLE')
 with pytest.raises(HTTPException):extract('embedded-office.eml',eml('source.xlsx',out.getvalue()))

@pytest.mark.parametrize('name,content',[('../escape.csv',b'x,y'),('payload.exe',b'MZbinary'),('payload.zip',b'PKbinary'),('legacy.xls',b'legacy'),('nested.eml',b'Subject: nested\n\nbody'),('renamed.txt',b'MZexecutable'),('macro.xlsm',b'PKmacro')])
def test_email_unsafe_attachment_formats_paths_and_magic_rejected(name,content):
 with pytest.raises(HTTPException) as error:extract('synthetic.eml',eml(name,content))
 assert error.value.status_code in {415,422}

@pytest.mark.parametrize('ext',['xls','pst','ost','msg'])
def test_legacy_financial_and_mail_formats_stay_explicitly_unsupported(ext):
 with pytest.raises(HTTPException) as error:extract('synthetic.'+ext,b'Not a supported safe converter input')
 assert error.value.status_code==415

def upload(h,c,ids,name,data,handling='ordinary',scope=''):
 return h.post(BASE+'/documents',params={'matter_id':ids['matter'],'file_name':name,'logical_key':'CONVERTER-'+name.replace('.','-'),'classification':handling,'clean_team_scope':scope,'resource_type':'financial','synthetic':True},content=data,headers={'origin':'https://firm.localhost','x-csrf-token':c,'content-type':'application/octet-stream'})

def memberships(sessions,ids,people):
 from kestrel.models import CleanTeamMembership
 from kestrel.services.auth import clock
 with sessions() as db:
  for uid in people:db.add(CleanTeamMembership(account_id=uid,matter_id=ids['matter'],scope='pricing',approved_by=ids['sme'],expires_at=clock()+3600))
  db.commit()

def test_new_hidden_formats_require_scoped_intake_and_bank_never_inherits_sources(env):
 from kestrel.models import SourceVersion
 h,sessions,ids,app=env;c=login(h).json()['csrf_token']
 assert upload(h,c,ids,'synthetic.xlsm',xlsm()).status_code==422
 assert upload(h,c,ids,'synthetic.xlsm',xlsm(),'clean_team','pricing').status_code==403
 memberships(sessions,ids,[ids['lawyer']]);r=upload(h,c,ids,'synthetic.xlsm',xlsm(),'clean_team','pricing');assert r.status_code==201,r.text;source=r.json()
 reader=h.get(BASE+'/documents/'+source['id']+'/reader');assert reader.status_code==200 and reader.json()['format']=='excel'
 with TestClient(app,base_url='https://bank.localhost') as bank:
  login(bank,'bank',origin='https://bank.localhost');denied=bank.get(BASE+'/documents/'+source['id']+'/reader');assert denied.status_code==403 and 'COMMENT_SECRET_914' not in denied.text
 with sessions() as db:assert db.scalar(select(func.count()).select_from(SourceVersion))==1

def test_email_staged_download_rechecks_source_download_permission_and_does_not_create_children(env):
 from kestrel.api.source_attachments import router
 from kestrel.models import SourceVersion,EthicalWall
 from test_lifecycle import propose,approve
 h,sessions,ids,app=env;app.include_router(router);c=login(h).json()['csrf_token'];memberships(sessions,ids,[ids['lawyer'],ids['sme']])
 r=upload(h,c,ids,'synthetic.eml',eml(),'clean_team','pricing');assert r.status_code==201,r.text;source=r.json();path=BASE+'/documents/'+source['id']+'/attachments'
 listing=h.get(path);assert listing.status_code==200,listing.text;assert listing.json()['attachments'][0]['state']=='staged_not_ingested'
 assert not listing.json()['can_download']
 assert h.get(path+'/1/download').status_code==403
 assert post(h,BASE+'/documents/'+source['id']+'/confirm',c,{'snapshot_hash':source['snapshot_hash'],'rationale':'Confirm entire original email and staged attachment restrictions'}).status_code==200
 download=h.get(path+'/1/download');assert download.status_code==200,download.text
 assert h.get(path).json()['can_download']
 assert download.content==b'entity,amount\nVireo,9007199254740993.125\n' and download.headers['content-type']=='application/octet-stream' and download.headers['x-content-type-options']=='nosniff'
 signing=propose(h,ids,'sign');assert approve(h,signing).status_code==200
 login(h);assert h.get(path+'/1/download').status_code==200
 with sessions() as db:assert db.scalar(select(func.count()).select_from(SourceVersion))==1;db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
 denied=h.get(path);assert denied.status_code==403 and 'evidence.csv' not in denied.text
 assert h.get(path+'/1/download').status_code==403

def test_client_own_upload_hidden_guard_and_separate_firm_intake_remain_enforced(env):
 from kestrel.models import SourceVersion
 h,sessions,ids,app=env
 with TestClient(app,base_url='https://client.localhost') as client:
  c=login(client,'client',origin='https://client.localhost').json()['csrf_token'];headers={'origin':'https://client.localhost','x-csrf-token':c,'content-type':'application/octet-stream'}
  def submit(handling):return client.post('/api/v1/client-uploads',params={'matter_id':ids['matter'],'file_name':'client.xlsm','synthetic':True,'handling':handling},content=xlsm(),headers=headers)
  assert submit('ordinary').status_code==422 and submit('clean_team').status_code==403
  memberships(sessions,ids,[ids['client']]);r=submit('clean_team');assert r.status_code==201,r.text;submission=r.json()
  assert client.get('/api/v1/client-uploads/'+submission['id']).status_code==200
  with sessions() as db:assert db.scalar(select(func.count()).select_from(SourceVersion))==0
  lawyer=login(h).json()['csrf_token'];assert post(h,'/api/v1/client-uploads/'+submission['id']+'/accept',lawyer,{'logical_key':'CLIENT-XLSM','rationale':'Intake must require current named scope for the accepting firm lawyer'}).status_code==403
  memberships(sessions,ids,[ids['lawyer']]);accepted=post(h,'/api/v1/client-uploads/'+submission['id']+'/accept',lawyer,{'logical_key':'CLIENT-XLSM','rationale':'Explicit separate firm intake preserving hidden original restrictions'})
  assert accepted.status_code==201,accepted.text;assert accepted.json()['classification']=='clean_team' and not accepted.json()['classification_confirmed']

def test_staged_attachment_download_withholds_names_and_bytes_if_clearance_changes_mid_read(env,monkeypatch):
 from kestrel.services import source_attachments as service
 from kestrel.models import CleanTeamMembership
 h,sessions,ids,_=env;c=login(h).json()['csrf_token'];memberships(sessions,ids,[ids['lawyer']])
 source=upload(h,c,ids,'race.eml',eml(),'clean_team','pricing').json()
 assert post(h,BASE+'/documents/'+source['id']+'/confirm',c,{'snapshot_hash':source['snapshot_hash'],'rationale':'Confirm exact synthetic parent before staged download race'}).status_code==200
 original=service.prepare
 def changed(db,actor,sid,download=False,historical=False):
  value=original(db,actor,sid,download,historical)
  with sessions() as other:
   other.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id==ids['lawyer'])).revoked=True;other.commit()
  return value
 monkeypatch.setattr(service,'prepare',changed)
 denied=h.get(BASE+'/documents/'+source['id']+'/attachments/1/download')
 assert denied.status_code in {403,409},denied.text
 assert 'evidence.csv' not in denied.text and '9007199254740993.125' not in denied.text and 'content-disposition' not in denied.headers
