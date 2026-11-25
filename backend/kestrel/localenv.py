"""Literal .env reader: no interpolation, shell execution or secret output."""
import json
import os
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]


def read_env(path=None):
    path=Path(path or os.environ.get('KESTREL_ENV_FILE',ROOT/'.env'))
    if not path.is_file():return {}
    values={}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        key,separator,value=line.partition('=')
        if not separator or not re.fullmatch(r'KESTREL_[A-Z0-9_]+',key):raise ValueError('Invalid local environment entry')
        value=value.strip()
        if value.startswith('"'):value=json.loads(value)
        elif len(value)>=2 and value[0]==value[-1]=="'":value=value[1:-1]
        values[key]=value
    return values


def load_env(path=None):
    values=read_env(path)
    for key,value in values.items():os.environ.setdefault(key,value)
    return values
