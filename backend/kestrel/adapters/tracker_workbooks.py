"""Formula-free portable workbook authoring with public Python dependencies."""
import io,json,subprocess
from fastapi import HTTPException
from kestrel.adapters import runtime
ROOT=runtime.ROOT


def build(payload,preview=False):
    try:
        data=json.dumps(payload).encode()
        if len(data)>2*1024*1024:raise ValueError()
        content=runtime.run_bytes([runtime.python(),ROOT/'scripts/portable_workbooks.py',*(['--preview'] if preview else [])],data=data,timeout=45,limit=3*1024*1024)
        if not content.startswith(b'PK') or len(content)>3*1024*1024:raise ValueError()
        # Verify exported strings cannot become executable Excel formulas.
        from openpyxl import load_workbook
        book=load_workbook(io.BytesIO(content),read_only=True,data_only=False,keep_links=False)
        try:
            if any(sheet.sheet_state!='visible' for sheet in book):raise ValueError()
            if any(c.data_type=='f' for sheet in book for row in sheet for c in row):raise ValueError()
        finally:book.close()
        return content
    except Exception:
        # Do not log builder stderr: it could contain workbook passages.
        raise HTTPException(503,'Workbook engine unavailable; verify the portable Python runtime') from None
