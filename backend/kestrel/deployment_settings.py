"""Owner-controlled runtime gate. No endpoint can create a public approval.

PUBLIC_DEMO is Windows, synthetic-only, single-process and reverse-proxy-only.
LOCAL keeps its original hosts and launcher. Public activation requires external
owner files whose ACLs, expiry, exact configuration, release and test hashes agree.
"""
from dataclasses import dataclass, field
from pathlib import Path
import ctypes
import hashlib
import ipaddress
import json
import os
import re
import time
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[2]
LOCAL_HOSTS={'localhost':'firm','127.0.0.1':'firm','testserver':'firm','admin.localhost':'firm',
    'firm.localhost':'firm','client.localhost':'halden','bank.localhost':'castlegate'}
PUBLIC_HOSTS={'portal.ramijaloudi.com':None,'firm.portal.ramijaloudi.com':'firm',
    'halden.portal.ramijaloudi.com':'halden','castlegate.portal.ramijaloudi.com':'castlegate','admin.portal.ramijaloudi.com':'firm'}
PUBLIC_LINKS={'home':'https://portal.ramijaloudi.com','admin':'https://admin.portal.ramijaloudi.com',
    'firm':'https://firm.portal.ramijaloudi.com','halden':'https://halden.portal.ramijaloudi.com','castlegate':'https://castlegate.portal.ramijaloudi.com'}
LOCAL_LINKS={'home':'https://localhost:8443','admin':'https://admin.localhost:8443','firm':'https://firm.localhost:8443',
    'halden':'https://client.localhost:8443','castlegate':'https://bank.localhost:8443'}


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def sha(value):return hashlib.sha256(value if isinstance(value,bytes) else value.encode()).hexdigest()


def release_hash():
    patterns=['backend/kestrel/**/*.py','backend/kestrel/swagger_session.js','backend/migrations/**/*.py','backend/alembic.ini',
        'backend/tests/test_*.py','backend/pyproject.toml','backend/requirements*.lock','backend/requirements*.txt',
        'frontend/dist/**/*','frontend/src/**/*','frontend/package*.json','scripts/*.py','scripts/*.mjs','scripts/*.ps1',
        'deployment/**/*','backend/kestrel/data/workflow_scripts/**/*']
    paths=sorted({p for pattern in patterns for p in ROOT.glob(pattern) if p.is_file() and '__pycache__' not in p.parts})
    if not paths or not (ROOT/'frontend/dist/index.html').is_file():raise RuntimeError('Reviewed release build required')
    return sha(canonical([(p.relative_to(ROOT).as_posix(),sha(p.read_bytes())) for p in paths]))


def test_suite_hash():
    paths=sorted((ROOT/'backend/tests').glob('test_*.py'))
    if not paths:raise RuntimeError('Reviewed acceptance test sources required')
    return sha(canonical([(p.relative_to(ROOT).as_posix(),sha(p.read_bytes())) for p in paths]))


def _read_json(path):
    if path.stat().st_size>32768:raise RuntimeError('Public owner file exceeds bound')
    def distinct(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise RuntimeError('Duplicate owner configuration field')
            value[key]=item
        return value
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=distinct)


def _external(path):
    value=Path(path)
    if not value.is_absolute() or value.is_symlink() or value.drive.startswith('\\\\'):raise RuntimeError('Absolute external local owner file required')
    resolved=value.resolve(strict=True)
    if resolved.is_relative_to(ROOT.resolve()):raise RuntimeError('Owner approval and proxy files must be outside the application')
    return resolved


def _windows_private_file(path,owner_sid,service_sid,readers):
    """Require protected explicit NTFS grants: owner/SYSTEM write, named readers read.

    This has no environment/test bypass. Isolated tests replace this OS boundary.
    The actual service SID must differ from the owner SID and match this process.
    """
    if os.name!='nt':raise RuntimeError('Public demo requires the reviewed Windows service runtime')
    if ctypes.windll.shell32.IsUserAnAdmin():raise RuntimeError('Nonadministrator application service required')
    from ctypes import wintypes
    adv=ctypes.windll.advapi32;kernel=ctypes.windll.kernel32
    adv.GetNamedSecurityInfoW.argtypes=[wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
    adv.GetAce.argtypes=[ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(ctypes.c_void_p)]
    adv.ConvertSidToStringSidW.argtypes=[ctypes.c_void_p,ctypes.POINTER(wintypes.LPWSTR)]
    adv.GetSecurityDescriptorControl.argtypes=[ctypes.c_void_p,ctypes.POINTER(wintypes.WORD),ctypes.POINTER(wintypes.DWORD)]
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    def sid(pointer):
        target=wintypes.LPWSTR()
        if not adv.ConvertSidToStringSidW(pointer,ctypes.byref(target)):raise RuntimeError('Owner ACL verification failed')
        try:return target.value
        finally:kernel.LocalFree(target)
    token=ctypes.c_void_p()
    adv.OpenProcessToken.argtypes=[wintypes.HANDLE,wintypes.DWORD,ctypes.POINTER(ctypes.c_void_p)]
    adv.GetTokenInformation.argtypes=[ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(),8,ctypes.byref(token)):raise RuntimeError('Service identity verification failed')
    try:
        size=wintypes.DWORD();adv.GetTokenInformation(token,1,None,0,ctypes.byref(size));buffer=ctypes.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token,1,buffer,size,ctypes.byref(size)):raise RuntimeError('Service identity verification failed')
        current=sid(ctypes.cast(buffer,ctypes.POINTER(ctypes.c_void_p))[0])
    finally:kernel.CloseHandle(token)
    if current!=service_sid or current==owner_sid:raise RuntimeError('Independent non-owner service identity required')
    owner=ctypes.c_void_p();dacl=ctypes.c_void_p();descriptor=ctypes.c_void_p()
    if adv.GetNamedSecurityInfoW(str(path),1,5,ctypes.byref(owner),None,ctypes.byref(dacl),None,ctypes.byref(descriptor)):raise RuntimeError('Owner ACL verification failed')
    try:
        control=wintypes.WORD();revision=wintypes.DWORD()
        if not adv.GetSecurityDescriptorControl(descriptor,ctypes.byref(control),ctypes.byref(revision)) or not control.value&0x1000 or not dacl or sid(owner)!=owner_sid:raise RuntimeError('Protected owner ACL required')
        header=ctypes.string_at(dacl,8);count=int.from_bytes(header[4:6],'little');seen=set()
        if not 1<=count<=8:raise RuntimeError('Bounded explicit owner ACL required')
        write_mask=0x10000000|0x40000000|0x000d0156
        for index in range(count):
            ace=ctypes.c_void_p()
            if not adv.GetAce(dacl,index,ctypes.byref(ace)):raise RuntimeError('Owner ACL verification failed')
            data=ctypes.string_at(ace,8)
            if data[0]!=0 or data[1]&0x10:raise RuntimeError('Only explicit owner and reader grants are supported')
            mask=int.from_bytes(data[4:8],'little');who=sid(ace.value+8);seen.add(who)
            if who in {owner_sid,'S-1-5-18'}:continue
            if who not in readers or mask&write_mask:raise RuntimeError('Service-readable owner files must not be service-writable')
        if service_sid not in seen:raise RuntimeError('Explicit service read grant required')
    finally:kernel.LocalFree(descriptor)


@dataclass(frozen=True)
class DeploymentSettings:
    mode:str='LOCAL'
    config:dict=field(default_factory=dict,repr=False)
    config_file:Path|None=None
    proxy_token:str=field(default='',repr=False)
    approval_expiry:int=0
    approval_hash:str=''
    receipt_hash:str=''
    @property
    def public(self):return self.mode=='PUBLIC_DEMO'
    @property
    def hosts(self):return dict(PUBLIC_HOSTS if self.public else LOCAL_HOSTS)
    @property
    def links(self):return dict(PUBLIC_LINKS if self.public else LOCAL_LINKS)
    @property
    def config_hash(self):return sha(canonical(self.config))
    def normalized_host(self,raw):
        if not isinstance(raw,str) or not raw.isascii() or not re.fullmatch(r'[A-Za-z0-9.-]+(?::[0-9]{1,5})?',raw):return None
        host,sep,port=raw.lower().partition(':')
        if self.public and sep and port!='443':return None
        if host not in self.hosts:return None
        return host
    def origin_matches(self,origin,host):
        try:
            value=urlsplit(origin)
            return value.scheme=='https' and not value.username and not value.password and not value.path and not value.query and not value.fragment and self.normalized_host(value.netloc)==host and (not self.public or value.port in {None,443})
        except (ValueError,TypeError):return False
    def site_config(self):
        return {'mode':self.mode,'synthetic_only':True,'links':self.links,'home_host':urlsplit(self.links['home']).hostname,
            'admin_host':urlsplit(self.links['admin']).hostname,'portals':[{'key':key,'host':urlsplit(self.links[key]).hostname,'org':org} for key,org in [('admin','firm'),('firm','firm'),('halden','halden'),('castlegate','castlegate')]]}
    def active(self):
        if not self.public:return True
        try:
            path=Path(self.config['approval_file'])
            receipt=Path(self.config['receipt_file'])
            return time.time()<self.approval_expiry and path.stat().st_size<=32768 and sha(path.read_bytes())==self.approval_hash and receipt.stat().st_size<=32768 and sha(receipt.read_bytes())==self.receipt_hash and sha(canonical(_read_json(self.config_file)))==self.config_hash
        except (OSError,KeyError,ValueError,TypeError,RuntimeError):return False


def load_deployment():
    mode=os.environ.get('KESTREL_ENV','LOCAL')
    if mode=='LOCAL':return DeploymentSettings()
    if mode!='PUBLIC_DEMO':raise RuntimeError('Public deployment blocked pending separate owner approval')
    path=_external(os.environ.get('KESTREL_PUBLIC_CONFIG',''))
    config=_read_json(path)
    required={'schema','mode','hosts','backend_host','backend_port','workers','owner_sid','service_sid','proxy_sid','proxy_token_file','approval_file','receipt_file'}
    if set(config)!=required or config['schema']!='kestrel-public-config-1' or config['mode']!='PUBLIC_DEMO' or config['hosts']!=PUBLIC_HOSTS or config['backend_host']!='127.0.0.1' or type(config['backend_port']) is not int or config['backend_port']!=8000 or type(config['workers']) is not int or config['workers']!=1:raise RuntimeError('Exact reviewed public configuration required')
    if any(not re.fullmatch(r'S-1-[0-9-]+',config[key]) for key in ['owner_sid','service_sid','proxy_sid']):raise RuntimeError('Explicit Windows owner/service/proxy identities required')
    if len({config['owner_sid'],config['service_sid'],config['proxy_sid']})!=3:raise RuntimeError('Separate owner, application and proxy identities required')
    owner,service,proxy=(config[k] for k in ['owner_sid','service_sid','proxy_sid'])
    approval_path=_external(config['approval_file']);receipt_path=_external(config['receipt_file']);token_path=_external(config['proxy_token_file'])
    for value in [path,approval_path,receipt_path]:_windows_private_file(value,owner,service,{service})
    _windows_private_file(token_path,owner,service,{service,proxy})
    if token_path.stat().st_size>256:raise RuntimeError('Proxy token file exceeds bound')
    token=token_path.read_text(encoding='ascii').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{43,128}',token):raise RuntimeError('Owner-generated random proxy token required')
    approval=_read_json(approval_path);receipt=_read_json(receipt_path);release=release_hash();tests=test_suite_hash();config_hash=sha(canonical(config));now=int(time.time())
    expected={'schema':'kestrel-public-approval-1','decision':'approve-public-synthetic-demo','owner_sid':owner,'mode':'PUBLIC_DEMO','hosts':PUBLIC_HOSTS,'config_hash':config_hash,'release_hash':release,'test_suite_hash':tests,'receipt_hash':sha(receipt_path.read_bytes())}
    if set(approval)!=set(expected)|{'approved_at','expires_at'} or any(approval.get(k)!=v for k,v in expected.items()):raise RuntimeError('Exact owner approval for this release/configuration/test receipt required')
    if any(type(approval.get(k)) is not int for k in ['approved_at','expires_at']) or not approval['approved_at']<=now<approval['expires_at']<=approval['approved_at']+7*86400:raise RuntimeError('Current bounded owner approval required')
    if receipt.get('schema')!='kestrel-public-acceptance-1' or receipt.get('release_hash')!=release or receipt.get('test_suite_hash')!=tests or receipt.get('config_hash')!=config_hash or receipt.get('all_required_passed') is not True or set(receipt.get('required_checks',[]))!={'backend_full','public_boundary','postgres_restore','frontend_build','tls_proxy','windows_services','backup_recovery','owner_review'}:raise RuntimeError('Complete matching public acceptance receipt required')
    return DeploymentSettings(mode,config,path,token,approval['expires_at'],sha(approval_path.read_bytes()),expected['receipt_hash'])


def settings_for(request):return getattr(getattr(getattr(request,'app',None),'state',None),'deployment',DeploymentSettings())


def navigation_url(request,url):
    """Only trusted authored navigation links call this; never evidence content."""
    settings=settings_for(request)
    if not settings.public:return url
    for key,prefix in LOCAL_LINKS.items():
        if url==prefix or url.startswith(prefix+'/'):return settings.links[key]+url[len(prefix):]
    return url
