import json,subprocess
from fastapi import HTTPException
from kestrel.adapters import runtime
ROOT=runtime.ROOT
def export(body,kind,status):
    payload=json.dumps({'body':body,'format':kind,'status':status}).encode()
    if kind not in {'pdf','docx','xlsx'}:raise HTTPException(422,'Choose PDF, Word or XLSX')
    if len(payload)>2*1024*1024:raise HTTPException(413,'Report payload exceeded bounds')
    try:
        content=runtime.run_bytes([runtime.python(),ROOT/'scripts/report_artifacts.py'],data=payload,timeout=45)
        if not content.startswith(b'%PDF-' if kind=='pdf' else b'PK'):raise OSError('Invalid renderer output')
        return content
    except (OSError,ValueError,subprocess.TimeoutExpired):raise HTTPException(503,'Report renderer unavailable or timed out') from None
