"""Local Windows CurrentUser DPAPI storage. Never return secret material to an API caller."""
import base64,ctypes,json,os
from ctypes import wintypes
from pathlib import Path
from fastapi import HTTPException
ROOT=Path(__file__).resolve().parents[3]
FILE=ROOT/'.runtime/ai-provider.json'
class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_byte))]
def crypt(data,protect):
    if os.name!='nt':raise HTTPException(503,'Windows secret protection is required for this local configuration')
    buffer=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_byte)));target=Blob()
    function=ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    ok=function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    if not ok:raise HTTPException(503,'Local secret protection unavailable')
    try:return ctypes.string_at(target.data,target.size)
    finally:
        free=ctypes.windll.kernel32.LocalFree;free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p;free(target.data)
def configured():
    if not FILE.exists():return None
    value=json.loads(FILE.read_text());key=crypt(base64.b64decode(value['protected_key']),False).decode() if value.get('protected_key') else ''
    return bool(value['enabled']),key
def save(key,enabled):
    prior=configured();key=key if key else prior[1] if prior else ''
    if enabled and not key:raise HTTPException(422,'A key must be saved before enabling live AI')
    value={'enabled':enabled,'protected_key':base64.b64encode(crypt(key.encode(),True)).decode() if key else ''}
    FILE.parent.mkdir(parents=True,exist_ok=True);temp=FILE.with_suffix('.tmp');temp.write_text(json.dumps(value));os.replace(temp,FILE)
