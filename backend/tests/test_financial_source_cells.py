import io,zipfile
import pytest
from fastapi import HTTPException
from test_auth_policy import env,login
from test_observability_governance import post

def workbook():
 from openpyxl import Workbook
 b=Workbook();b.active.title='Visible';b.active.append(['Entity','Metric','Amount','FY2025 EUR units IFRS consolidated']);b.active.append(['Vireo','revenue',12]);b.active['D2']='=C2*1000';b.create_sheet('Restricted').sheet_state='veryHidden'
 b['Restricted']['A1']='SYNTHETIC_HIDDEN_881'
 stream=io.BytesIO();b.save(stream)
 out=io.BytesIO()
 with zipfile.ZipFile(stream) as src,zipfile.ZipFile(out,'w') as dst:
  for f in src.infolist():
   data=src.read(f.filename)
   if f.filename=='xl/worksheets/sheet1.xml':data=data.replace(b'<v>12</v>',b'<v>9007199254740993.125</v>').replace(b'<f>C2*1000</f><v></v>',b'<f>C2*1000</f><v>9007199254740993125</v>')
   dst.writestr(f,data)
 return out.getvalue()

def test_numeric_xml_precision_formula_cache_and_hidden_cell_anchors():
 from kestrel.adapters.extraction import extract
 from kestrel.adapters.document_reader import presentation
 from types import SimpleNamespace
 import json
 data=workbook();r=extract('synthetic.xlsx',data)
 row=next(u for u in r['units'] if u['locator']=='Visible, row 2')
 assert '9007199254740993.125' in row['text']
 cells={c['coordinate']:c for c in row['cells']}
 assert cells['C2']['raw_value']=='9007199254740993.125'
 assert cells['D2']['formula']=='C2*1000' and cells['D2']['cached_value']=='9007199254740993125'
 assert cells['D2']['formula_ast']['kind']=='binary'
 assert row['text'][cells['C2']['start']:cells['C2']['end']]=='9007199254740993.125'
 assert next(u for u in r['units'] if u['sheet']=='Restricted')['sheet_state']=='veryHidden'
 reader=presentation(SimpleNamespace(file_name='synthetic.xlsx',data=data,units_json=json.dumps(r['units'])))
 assert reader['sheets'][0]['rows'][1]['cells'][2]['text']=='9007199254740993.125'
 assert reader['sheets'][1]['state']=='veryHidden'

def test_formula_parser_never_evaluates_or_trusts_unsupported_functions():
 from kestrel.adapters.spreadsheet_source import formula_ast
 assert formula_ast('SUM(A1:A3)+1.2500')['kind']=='binary'
 with pytest.raises(ValueError):formula_ast('WEBSERVICE("https://example.invalid")')
 with pytest.raises(ValueError):formula_ast('1+'*1000+'1')

def test_csv_rows_exact_strings_and_safe_unsupported_formats():
 from kestrel.adapters.extraction import extract
 r=extract('synthetic.csv','entity,amount\nVireo,9007199254740993.125\n'.encode())
 assert r['units'][1]['locator']=='CSV row 2' and r['units'][1]['cells'][1]['raw_value']=='9007199254740993.125'
 with pytest.raises(HTTPException) as e:extract('synthetic.xls',workbook())
 assert e.value.status_code==415

def test_financial_dimensions_can_cite_header_and_numeric_row_without_float_rounding(env):
 from test_document_workflow import BASE
 from test_financial_workflow import payload,F
 h,sessions,ids,_=env;c=login(h).json()['csrf_token']
 from test_financial_converters import memberships
 memberships(sessions,ids,[ids['lawyer']])
 r=h.post(BASE+'/documents',params={'matter_id':ids['matter'],'file_name':'synthetic.xlsx','logical_key':'FIN-XLSX-001','classification':'clean_team','clean_team_scope':'pricing','resource_type':'financial','synthetic':True},content=workbook(),headers={'origin':'https://firm.localhost','x-csrf-token':c,'content-type':'application/octet-stream'})
 assert r.status_code==201,r.text;s=r.json();assert post(h,BASE+'/documents/'+s['id']+'/confirm',c,{'snapshot_hash':s['snapshot_hash'],'rationale':'Confirm synthetic exact workbook for evidence capture'}).status_code==200
 units=h.get(BASE+'/documents/'+s['id']+'/reader').json()['units'];row=next(u for u in units if u['locator']=='Visible, row 2');header=units[0]
 p={**payload(s['id'],row['text']),'unit':row['number']}
 assert post(h,F+'/facts',c,p).status_code==422
 p['context_spans']=[{'unit':header['number'],'start':0,'end':len(header['text'])}]
 r=post(h,F+'/facts',c,p);assert r.status_code==201,r.text
 assert r.json()['amount_text']=='9007199254740993.125' and r.json()['evidence']['dimension_contexts'][0]['locator']=='Visible, row 1'
 assert post(h,F+'/facts',c,p).json()['id']==r.json()['id']
