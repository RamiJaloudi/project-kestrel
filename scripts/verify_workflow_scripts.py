"""Offline launcher preflight; never generates or changes retained workbooks."""
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

ASSETS = Path(__file__).resolve().parents[1] / 'backend/kestrel/data/workflow_scripts'


def verify():
    raw = (ASSETS / 'catalog.json').read_bytes()
    catalog = json.loads(raw)
    manifest = json.loads((ASSETS / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'kestrel-workflow-templates-1' or manifest.get('catalog_sha256') != sha256(raw).hexdigest():
        raise ValueError('Workbook catalog verification failed')
    expected = {row['id'] + ':' + row['variant']: len(row['steps']) for row in catalog['guides']}
    if set(expected) != set(manifest['templates']):
        raise ValueError('Workbook catalog coverage mismatch')
    for key, record in manifest['templates'].items():
        name = record['file']
        if Path(name).name != name or not name.endswith('.xlsx'):
            raise ValueError('Invalid workbook filename')
        content = (ASSETS / name).read_bytes()
        if sha256(content).hexdigest() != record['sha256'] or record['steps'] != expected[key]:
            raise ValueError('Workbook verification failed')
        with ZipFile(BytesIO(content)) as book:
            if 'xl/worksheets/sheet1.xml' not in book.namelist():
                raise ValueError('Workbook sheet missing')
    return len(expected)


if __name__ == '__main__':
    try:
        count = verify()
        print(f'Excel workflow scripts verified: {count} role-specific templates. Resources downloads are ready.')
    except (OSError, ValueError, KeyError):
        print('Excel workflow scripts are missing or inconsistent. Restore the reviewed template bundle before starting.')
        raise SystemExit(1)
