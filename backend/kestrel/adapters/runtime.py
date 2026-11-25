"""Portable administrator-controlled runtime selection. Never downloads tools."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def settings():
    config = ROOT / '.runtime/portable-runtime.json'
    value = json.loads(config.read_text(encoding='utf-8-sig')) if config.exists() else {}
    if not isinstance(value, dict):
        raise ValueError('Invalid portable runtime settings')
    return value


def option(name, default=None):
    return os.environ.get('KESTREL_' + name.upper()) or settings().get(name.lower(), default)


def executable(name, default):
    found = shutil.which(str(option(name, default)))
    if found and Path(found).is_file():
        return Path(found).resolve()
    raise OSError('Configured runtime executable is unavailable')


def python():
    return executable('report_python', sys.executable)


def ocr_models():
    return Path(option('ocr_models', str(ROOT / '.runtime/ocr-models')))


def legacy_ocr_node():
    """Preserve the installed local JS baseline without a hardcoded bundle path."""
    config = ROOT / '.runtime/tracker-workbook-runtime.json'
    old = json.loads(config.read_text(encoding='utf-8-sig')) if config.exists() else {}
    node = executable('ocr_node', old.get('node', 'node'))
    modules = Path(option('ocr_node_modules', old.get('modules', '')))
    if not (modules / 'tesseract.js/package.json').is_file():
        raise OSError('Tesseract.js is unavailable')
    return node, modules.resolve()


def run_bytes(command, *, data=None, timeout=45, limit=20 * 1024 * 1024, env=None):
    """Bound subprocess lifetime/output; sensitive stderr is never surfaced."""
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        result = subprocess.run(
            [str(item) for item in command], input=data, stdout=output, stderr=errors,
            timeout=timeout, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        if result.returncode or output.tell() > limit:
            raise OSError('Runtime operation failed or exceeded output bounds')
        output.seek(0)
        return output.read(limit + 1)
