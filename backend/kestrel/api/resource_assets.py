"""Authenticated authored assets only. Never expose an arbitrary filesystem path."""
import hashlib
import json
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from kestrel.api.auth import database, identity
from kestrel.api.resources import resource_response

router = APIRouter(prefix='/api/v1/resources/assets', tags=['Project resource library'])
LIBRARY = Path(__file__).resolve().parents[1] / 'data/resource_library'


def catalogue():
    try:
        entries = json.loads((LIBRARY / 'catalog.json').read_text(encoding='utf-8'))['assets']
        if not isinstance(entries, list): raise ValueError('Invalid catalogue')
        ids = [entry['id'] for entry in entries]
        if len(ids) != len(set(ids)): raise ValueError('Duplicate asset identifiers')
        for entry in entries:
            if not re.fullmatch(r'[a-z0-9-]+', entry['id']): raise ValueError('Invalid identifier')
            filename = entry['filename']
            if not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', filename) or Path(filename).name != filename:
                raise ValueError('Invalid filename')
            if not re.fullmatch(r'[a-f0-9]{64}', entry['sha256']): raise ValueError('Invalid digest')
        return entries
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Resource library unavailable') from None


@router.get('')
def list_assets(request: Request, category: str | None = None, actor=Depends(identity), db=Depends(database)):
    def prepare(fresh, permitted):
        return [{**{key: value for key, value in entry.items() if key != 'filename'},
                 'download_href': f"/api/v1/resources/assets/{entry['id']}/download"}
                for entry in catalogue() if fresh.org.value in entry['audiences']
                and (category is None or entry['category'] == category)]
    return resource_response(db, request, prepare)


@router.get('/{asset_id}/download')
def download_asset(asset_id: str, request: Request, actor=Depends(identity), db=Depends(database)):
    def prepare(fresh, permitted):
        entry = next((item for item in catalogue() if item['id'] == asset_id), None)
        # Do not reveal internal asset existence to an external organization.
        if entry is None or fresh.org.value not in entry['audiences']:
            raise HTTPException(404, 'Resource not found')
        try:
            candidate = LIBRARY / entry['filename']
            if candidate.is_symlink(): raise ValueError('Invalid path')
            path = candidate.resolve(strict=True)
            if path.parent != LIBRARY.resolve(): raise ValueError('Invalid path')
            if path.stat().st_size != entry['bytes'] or path.stat().st_size > 25_000_000:
                raise ValueError('Invalid size')
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise ValueError('Asset changed')
        except (OSError, ValueError):
            raise HTTPException(503, 'Resource unavailable; refresh the library') from None
        return Response(data, media_type=entry['media_type'], headers={
            'Content-Disposition': f'attachment; filename="{entry["filename"]}"',
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'X-Asset-SHA256': entry['sha256'], 'Content-Security-Policy': "sandbox; default-src 'none'"})
    return resource_response(db, request, prepare)
