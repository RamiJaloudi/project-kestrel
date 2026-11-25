import json,os,subprocess
from fastapi import HTTPException
from kestrel.adapters import runtime
ROOT=runtime.ROOT
def render(rows,actor,filters):
    try:
        content=runtime.run_bytes([runtime.python(),ROOT/'scripts/audit_pdf.py'],data=json.dumps({'rows':rows,'exported_by':actor.id,'filters':filters}).encode(),timeout=30)
        if not content.startswith(b'%PDF'):raise HTTPException(503,'Audit PDF renderer unavailable or exceeded limits')
        return content
    except (OSError,subprocess.TimeoutExpired):raise HTTPException(503,'Audit PDF runtime unavailable or timed out')
