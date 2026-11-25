"""Read-only runtime preflight. Does not read secrets, databases or cloud accounts."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from kestrel.adapters import ocr,runtime


def check(require_native=False):
    result={'scope':'runtime-only; not public deployment acceptance','azure_cli_installed':bool(shutil.which('az'))}
    try:
        command=[runtime.python(),'-c',"import json,importlib.metadata; print(json.dumps({p:importlib.metadata.version(p) for p in ['openpyxl','python-docx','reportlab','pypdf','Pillow']}))"]
        result['report_packages']=json.loads(runtime.run_bytes(command,timeout=10,limit=4096))
        result['reports_available']=True
    except (OSError,ValueError,subprocess.TimeoutExpired):result['reports_available']=False
    try:
        _,engine,recognizer,modules=ocr.components();ocr.verify_models()
        if engine=='native':
            version=runtime.run_bytes([recognizer,'--version'],timeout=5,limit=4096).decode('utf-8',errors='replace').splitlines()[0]
            if not version.startswith('tesseract 5.'):raise ValueError('Tesseract 5 required')
            result['ocr_version']=version
        elif json.loads((modules/'tesseract.js/package.json').read_text(encoding='utf-8')).get('version')!='7.0.0':raise ValueError('Tesseract.js 7.0.0 required')
        result.update(ocr_available=True,ocr_engine=engine,ocr_models_commit=ocr.MODEL_COMMIT)
    except (OSError,ValueError,KeyError,TypeError,IndexError,subprocess.TimeoutExpired):result.update(ocr_available=False,ocr_engine=None)
    result['native_ocr_required']=require_native
    result['passed']=result['reports_available'] and result['ocr_available'] and (not require_native or result['ocr_engine']=='native')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-native',action='store_true',help='Fail if the native Tesseract target is not configured')
    args=parser.parse_args();result=check(args.require_native)
    print(json.dumps(result,indent=2));sys.exit(0 if result['passed'] else 1)
