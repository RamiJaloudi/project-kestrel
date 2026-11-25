import ssl
import sys
import urllib.request
import json
import time
import os
from pathlib import Path

def context():return ssl.create_default_context(cafile=str(Path(__file__).resolve().parents[1]/'.runtime/local-ca.pem'))

def process_alive(pid):
    if type(pid) is not int or pid<=0:return False
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.windll.kernel32
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:return False
        try:
            code=wintypes.DWORD();return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code)) and code.value==259)
        finally:kernel.CloseHandle(handle)
    try:os.kill(pid,0);return True
    except OSError:return False

def healthy(check_components=False):
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context()))
        for url in ['https://localhost:8443/health/ready','http://localhost:8000/health/ready']:
            with opener.open(url,timeout=3) as response:
                if response.status!=200 or not response.url.startswith('https://localhost:8443/'):return False
        if check_components:
            directory=Path(__file__).resolve().parents[1]/'.runtime/status'
            supervisor=json.loads((directory/'supervisor.json').read_text())
            if supervisor['health'] not in {'starting','ready'} or not process_alive(supervisor['pid']):return False
            for component in ['https','http','worker','postgres','monitor']:
                row=json.loads((directory/(component+'.json')).read_text())
                if row['health']!='ready' or int(time.time())-row['at']>25 or row.get('supervisor_run')!=supervisor['run_id'] or not process_alive(row['pid']):return False
        return True
    except Exception:return False

if __name__=='__main__':sys.exit(0 if healthy(check_components=True) else 1)
