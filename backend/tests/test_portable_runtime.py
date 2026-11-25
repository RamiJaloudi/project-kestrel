"""No DB fixtures: portable renderer and OCR boundary contracts."""
import io
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from openpyxl import load_workbook
from pypdf import PdfReader, PdfWriter
from kestrel.adapters import runtime, report_export, tracker_workbooks, ocr, disclosure, audit_pdf


def body():
    row={'reference':'SYN-001','finding':'Zustimmung erforderlich. Übertragung nur mit Einwilligung.','severity':'high','materiality':'material','requirement':'consent','action':'=HYPERLINK("https://example.invalid","literal")','status':'open','due_on':'2026-12-01'}
    return {'title':'Synthetic Project Kestrel report','overview':'Fictional English and German export verification.','coverage':'Synthetic subset only. No complete diligence coverage.','sections':[{'heading':'Assignment consent','text':'Übertragung requires review and written consent.','reference':'SYN-001 page 1'}],'risks':[row],'consents':[row]}


@pytest.mark.parametrize('kind',['pdf','docx','xlsx'])
def test_report_formats_without_node_or_bundle(kind,monkeypatch):
    monkeypatch.setenv('KESTREL_REPORT_PYTHON',sys.executable)
    content=report_export.export(body(),kind,'Synthetic draft')
    if kind=='pdf':
        text=' '.join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)
        assert 'Übertragung' in text and 'SYN-001' in text
    elif kind=='docx':
        from docx import Document
        document=Document(io.BytesIO(content))
        assert any('Übertragung' in paragraph.text for paragraph in document.paragraphs)
    else:
        book=load_workbook(io.BytesIO(content),data_only=False)
        assert book.sheetnames==['Risk annex','Consent annex']
        assert book['Risk annex']['F3'].value.startswith('=HYPERLINK')
        assert book['Risk annex']['F3'].data_type=='s'
        assert all(cell.data_type!='f' for sheet in book for row in sheet for cell in row)
        book.close()


@pytest.mark.parametrize('text',['=1+1','+SUM(A1:A2)','-1+1','@SUM(A1)','\t=1+1','\r=1+1','\n=1+1',"'already literal"])
def test_tracker_literal_contract_dates_and_visible_sheets(text):
    content=tracker_workbooks.build({'sheets':[{'name':'Records','rows':[['RecordID','ExpectedRevision','Action','DueOn'],['SYN-1',0,text,'2026-12-01']],'editable':['Action']}]})
    book=load_workbook(io.BytesIO(content),data_only=False)
    sheet=book['Records']
    assert sheet['C2'].value==text and sheet['C2'].data_type=='s'
    assert isinstance(sheet['D2'].value,datetime)
    assert sheet['B2'].value==0 and sheet.freeze_panes=='A2'
    assert sheet.sheet_state=='visible'
    assert not any(item.hidden for item in sheet.row_dimensions.values())
    book.close()


@pytest.mark.parametrize('payload',[{'existing':'pretend active content'},{'sheets':[{'name':'../escape','rows':[['x']]}]},{'sheets':[{'name':'Records','rows':[['x']]*506}]},{'sheets':[{'name':'Records','rows':[['x'],['x','y']]}]}])
def test_tracker_rejects_existing_packages_paths_and_unbounded_shapes(payload):
    with pytest.raises(HTTPException) as error:tracker_workbooks.build(payload)
    assert error.value.status_code==503


def test_subprocess_timeout_and_output_limit():
    with pytest.raises(subprocess.TimeoutExpired):runtime.run_bytes([sys.executable,'-c','import time; time.sleep(5)'],timeout=.05)
    with pytest.raises(OSError):runtime.run_bytes([sys.executable,'-c','print("x"*100)'],limit=10)


def test_runtime_explicit_invalid_executable_fails_closed(monkeypatch,tmp_path):
    monkeypatch.setenv('KESTREL_REPORT_PYTHON',str(tmp_path/'missing.exe'))
    with pytest.raises(HTTPException) as error:report_export.export(body(),'pdf','Synthetic')
    assert error.value.status_code==503


def test_disclosure_physical_validation_and_audit_renderer():
    units=[{'number':1,'locator':'Sanitized section 1','text':'Übertragung [REDACTED]. Synthetic agreement remains.'}]
    content=disclosure.render('Synthetic disclosure',units)
    assert disclosure.validate(content,'Synthetic disclosure',units,['Synthetic secret removed'])['passed']
    data=audit_pdf.render([{'occurred_at':0,'actor_id':'synthetic-lawyer','clean_team_scope':None,'action':'test.portability','outcome':'allowed','object_id':'SYN-1','id':'SYN-EVENT'}],SimpleNamespace(id='synthetic-auditor'),{'synthetic':True})
    assert 'test.portability' in ''.join(page.extract_text() for page in PdfReader(io.BytesIO(data)).pages)


def test_ocr_rejects_substituted_manifest_before_execution(monkeypatch,tmp_path):
    monkeypatch.setenv('KESTREL_OCR_MODELS',str(tmp_path))
    (tmp_path/'manifest.json').write_text(json.dumps({'commit':'different','models':{}}))
    with pytest.raises(ValueError):ocr.verify_models()


def test_native_ocr_pipeline_contract_with_stubbed_binary(monkeypatch,tmp_path):
    """Checks native argv/provenance, not a claim that Tesseract is installed."""
    from PIL import Image
    writer=PdfWriter();writer.add_blank_page(width=612,height=792);source=io.BytesIO();writer.write(source)
    monkeypatch.setattr(ocr,'components',lambda:(Path('pdftoppm'),'native',Path('tesseract'),None))
    monkeypatch.setattr(ocr,'verify_models',lambda:tmp_path)
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        if '--version' in command:return b'tesseract 5.5.1\n'
        if str(command[0])=='pdftoppm':Image.new('RGB',(100,120),'white').save(str(command[-1])+'.png');return b''
        assert command[2]=='stdout' and command[-1]=='tsv' and kwargs['env']['OMP_THREAD_LIMIT']=='1'
        return b'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t2\t3\t40\t10\t95.0\tConsent\n'
    monkeypatch.setattr(runtime,'run_bytes',run)
    result=ocr.extract_pdf(source.getvalue())
    assert result['extractor'].startswith('ocr:tesseract 5.5.1;eng+deu;')
    assert result['units'][0]['words'][0]['start']==0
    assert result['units'][0]['image_width']==100
    assert len(calls)==3
