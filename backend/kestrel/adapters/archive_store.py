"""Local protected archive adapter. Append-only creation is not external WORM storage."""
import os
from pathlib import Path
from uuid import uuid4,UUID
from fastapi import HTTPException
from kestrel.adapters.provider_secrets import crypt
from kestrel.adapters.extraction import digest
ROOT=Path(__file__).resolve().parents[3]/'.runtime/archives'
MAX_BYTES=50*1024*1024

def path(key):
    try:
        if str(UUID(key))!=key:raise ValueError()
    except ValueError:raise HTTPException(404,'Archive unavailable')
    return ROOT/(key+'.dpapi')

def put(content,*,require_worm=False):
    if require_worm:raise HTTPException(503,'Immutable external storage adapter is not configured; local storage cannot satisfy WORM')
    if not content or len(content)>MAX_BYTES:raise HTTPException(413,'Local archive limit is 50 MiB')
    key=str(uuid4());protected=crypt(content,True);ROOT.mkdir(parents=True,exist_ok=True)
    with path(key).open('xb') as output:output.write(protected);output.flush();os.fsync(output.fileno())
    return key,digest(protected),digest(content)

def get(key,protected_hash,plain_hash):
    target=path(key)
    if not target.is_file() or target.stat().st_size>MAX_BYTES+1024*1024:raise HTTPException(409,'Archive unavailable or exceeds bounds')
    data=target.read_bytes()
    if digest(data)!=protected_hash:raise HTTPException(409,'Protected archive integrity mismatch')
    content=crypt(data,False)
    if digest(content)!=plain_hash:raise HTTPException(409,'Archive content integrity mismatch')
    return content
