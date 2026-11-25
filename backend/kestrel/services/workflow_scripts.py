"""Portable delivery of authored, role-filtered Excel workflow scripts.

Templates are authored offline. Runtime adds only allowlisted navigation links;
no document, account, approval or credential values enter the workbook.
"""
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED


ASSETS = Path(__file__).resolve().parents[1] / 'data' / 'workflow_scripts'
MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PACKAGE = 'http://schemas.openxmlformats.org/package/2006/relationships'
MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


@lru_cache(maxsize=1)
def catalog():
    data = json.loads((ASSETS / 'catalog.json').read_text(encoding='utf-8'))
    if data.get('schema') != 'kestrel-workflow-scripts-1':
        raise RuntimeError('Workflow script catalog unavailable')
    return data['guides']


def script_for(guide_id, org):
    choices = [row for row in catalog() if row['id'] == guide_id]
    preferred = 'firm' if org == 'firm' else 'external'
    for variant in [org, preferred, 'default']:
        match = next((row for row in choices if row['variant'] == variant), None)
        if match is not None:
            return match
    raise KeyError(guide_id)


def navigation_target(step, org, settings):
    portal = step['portal']
    if portal == 'current':
        portal = org
    if portal not in {'firm', 'admin', 'halden', 'castlegate'}:
        raise RuntimeError('Workflow navigation unavailable')
    return settings.links[portal] + '/portal?view=' + quote(step['view'], safe='')


def workbook_bytes(guide_id, org, settings):
    script = script_for(guide_id, org)
    manifest = json.loads((ASSETS / 'manifest.json').read_text(encoding='utf-8'))
    key = guide_id + ':' + script['variant']
    retained = manifest['templates'][key]
    # Catalog IDs are still checked before a path is constructed. API callers
    # must separately pass the current Resources visibility decision.
    filename = retained['file']
    if Path(filename).name != filename or not filename.endswith('.xlsx'):
        raise RuntimeError('Workflow template unavailable')
    raw = (ASSETS / filename).read_bytes()
    catalog_hash = sha256((ASSETS / 'catalog.json').read_bytes()).hexdigest()
    if manifest['catalog_sha256'] != catalog_hash or sha256(raw).hexdigest() != retained['sha256']:
        raise RuntimeError('Workflow template verification failed')
    result = BytesIO()
    with ZipFile(BytesIO(raw)) as source, ZipFile(result, 'w', ZIP_DEFLATED) as target:
        if len(source.infolist()) > 60 or sum(row.file_size for row in source.infolist()) > 2_000_000:
            raise RuntimeError('Workflow template exceeds bound')
        sheet = ET.fromstring(source.read('xl/worksheets/sheet1.xml'))
        links = ET.Element('{' + MAIN + '}hyperlinks')
        relationships = ET.Element('{' + PACKAGE + '}Relationships')
        for index, step in enumerate(script['steps']):
            relationship = 'workflow' + str(index + 1)
            ET.SubElement(links, '{' + MAIN + '}hyperlink', {
                'ref': 'E' + str(retained['first_step_row'] + index),
                '{' + REL + '}id': relationship,
            })
            ET.SubElement(relationships, '{' + PACKAGE + '}Relationship', {
                'Id': relationship, 'Type': REL + '/hyperlink',
                'Target': navigation_target(step, org, settings), 'TargetMode': 'External',
            })
        # OOXML hyperlinks follow data validations and precede print settings.
        before = {'printOptions', 'pageMargins', 'pageSetup', 'headerFooter',
                  'rowBreaks', 'colBreaks', 'drawing', 'legacyDrawing', 'extLst'}
        insertion = next((i for i, child in enumerate(sheet) if child.tag.split('}')[-1] in before), len(sheet))
        sheet.insert(insertion, links)
        # Runtime authors no formulas. The offline artifact library has no
        # native-link API; this bounded OOXML addition supplies actual links.
        for entry in source.infolist():
            if entry.filename == 'xl/worksheets/sheet1.xml':
                target.writestr(entry, ET.tostring(sheet, encoding='utf-8', xml_declaration=True))
            elif entry.filename != 'xl/worksheets/_rels/sheet1.xml.rels':
                target.writestr(entry, source.read(entry.filename))
        target.writestr('xl/worksheets/_rels/sheet1.xml.rels',
                        ET.tostring(relationships, encoding='utf-8', xml_declaration=True))
    return result.getvalue()
