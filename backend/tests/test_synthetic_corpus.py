import hashlib
import json
from pathlib import Path
import io
import zipfile
import pytest
from fastapi import HTTPException
from kestrel.adapters.extraction import extract

ROOT=Path(__file__).resolve().parents[2]/'data/synthetic_waves'

def test_both_waves_have_valid_originals_and_no_fake_scan_coverage():
    ready=ocr=0
    hashes={}
    for wave,count in [(1,5),(2,6)]:
        manifest=json.loads((ROOT/f'Wave_{wave}/manifest.json').read_text(encoding='utf-8'))
        assert len(manifest['documents'])==count
        for entry in manifest['documents']:
            file=ROOT/f'Wave_{wave}'/entry['file_name'];data=file.read_bytes()
            assert hashlib.sha256(data).hexdigest()==entry['sha256']
            output=extract(file.name,data)
            assert output['bytes_hash']==entry['sha256']
            if entry['scan']:
                assert output['status']=='ocr_required';ocr+=1
            else:
                assert output['status']=='ready';ready+=1
            if entry['logical_key']=='L001':
                assert entry['language']=='de' and entry['governing_law']=='England and Wales'
                assert 'Zustimmung' in '\n'.join(u['text'] for u in output['units'])
            hashes[(wave,entry['logical_key'])]=entry['sha256']
    assert ready==9 and ocr==2
    assert hashes[(1,'C001')]!=hashes[(2,'C001')]
    assert hashes[(1,'P001')]!=hashes[(2,'P001')]

def test_macro_or_external_office_relationships_are_rejected():
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('word/document.xml','<document/>')
        archive.writestr('word/_rels/document.xml.rels','<Relationship TargetMode="External" Target="https://evil.example"/>')
    with pytest.raises(HTTPException):extract('synthetic.docx',output.getvalue())
