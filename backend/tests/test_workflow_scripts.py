"""Resources workbook authorization and package safety; isolated fixtures only.

Templates are authored by the application build, not by these tests. Package
inspection does not evaluate formulas, macros or external workbook content.
"""
from io import BytesIO
import json
import shutil
from urllib.parse import urlsplit
from zipfile import ZipFile
import pytest
from defusedxml import ElementTree as ET
from openpyxl import load_workbook
from sqlalchemy import delete
from fastapi.testclient import TestClient
from test_auth_policy import env,login,PASSWORD
from test_public_deployment import public_env,client as public_client,login as public_login
from kestrel import models as m
from kestrel.services.auth import clock
from kestrel.api import resources

BASE='/api/v1/resources'
MIME='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
SHEET='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
LOCAL_HOSTS={'localhost','admin.localhost','firm.localhost','client.localhost','bank.localhost'}
PUBLIC_HOSTS={'portal.ramijaloudi.com','admin.portal.ramijaloudi.com','firm.portal.ramijaloudi.com','halden.portal.ramijaloudi.com','castlegate.portal.ramijaloudi.com'}


def workbook(response,guide,*,public=False):
    assert response.status_code==200,response.text[:300] if not response.content.startswith(b'PK') else 'Unexpected workbook response'
    assert response.headers['content-type'].split(';')[0]==MIME
    assert response.headers['content-disposition']==f'attachment; filename="kestrel-{guide}-workflow.xlsx"'
    assert response.headers.get('cache-control')=='no-store'
    assert response.content.startswith(b'PK')
    with ZipFile(BytesIO(response.content)) as archive:
        names=archive.namelist();lower=[name.lower() for name in names]
        assert '[Content_Types].xml' in names and 'xl/workbook.xml' in names
        assert not any('vbaproject' in name or name.startswith(('xl/externallinks/','xl/macrosheets/','xl/dialogsheets/','xl/embeddings/')) for name in lower)
        assert b'macroenabled' not in archive.read('[Content_Types].xml').lower()
        definition=ET.fromstring(archive.read('xl/workbook.xml'))
        assert definition.find(f'{{{SHEET}}}externalReferences') is None
        for name in definition.findall(f'.//{{{SHEET}}}definedName'):
            assert name.attrib.get('name') not in {'Auto_Open','Auto_Close','_xlnm.Auto_Open','_xlnm.Auto_Close'}
        sheets=[name for name in names if name.startswith('xl/worksheets/') and name.endswith('.xml')]
        assert sheets
        texts=[];rows=0;cells=0
        for name in names:
            if not name.endswith('.xml'):continue
            root=ET.fromstring(archive.read(name))
            if name in sheets:
                assert root.find(f'.//{{{SHEET}}}f') is None,'Static workflow workbooks must not contain executable cell formulas'
                rows+=len(root.findall(f'.//{{{SHEET}}}sheetData/{{{SHEET}}}row'))
                cells+=len(root.findall(f'.//{{{SHEET}}}c'))
            texts.extend(node.text for node in root.iter() if node.text)
        links=[]
        for name in names:
            if not name.endswith('.rels'):continue
            for rel in ET.fromstring(archive.read(name)).findall(f'{{{REL}}}Relationship'):
                target=rel.attrib.get('Target','');kind=rel.attrib.get('Type','')
                if rel.attrib.get('TargetMode')=='External':
                    assert kind.endswith('/hyperlink'),'External workbook/embedded relationships are prohibited'
                    parsed=urlsplit(target)
                    assert parsed.scheme=='https' and parsed.hostname in (PUBLIC_HOSTS if public else LOCAL_HOSTS)
                    assert not parsed.username and not parsed.password
                    assert parsed.port in ({None,443} if public else {None,443,8443})
                    links.append(target)
        assert links,'Workflow steps need real browser hyperlinks, not formula text or relative file paths'
        text='\n'.join(texts)
        assert rows>=5 and cells>=12 and 'step' in text.lower(),'Expected an actual step-based workflow, not a renamed Markdown document'
        # A package can contain orphan hyperlink relationships; also prove Excel
        # worksheet cells expose real clickable links. This parser evaluates no
        # formulas, macros or network resources.
        book=load_workbook(BytesIO(response.content),data_only=False,keep_links=False)
        try:
            assert book.worksheets and all(sheet.sheet_state=='visible' for sheet in book.worksheets)
            cell_links=[cell.hyperlink.target for sheet in book.worksheets for row in sheet for cell in row if cell.hyperlink]
            assert cell_links and set(cell_links)<=set(links)
        finally:book.close()
        return text,links


def named(sessions,ids,who='lawyer',**changes):
    with sessions() as db:
        values={'account_id':ids[who],'matter_id':ids['matter'],'scope':'pricing','approved_by':ids['sme'],'starts_at':clock()-60,'expires_at':clock()+600,**changes}
        grant=m.CleanTeamMembership(**values)
        db.add(grant);db.commit();return grant.id


def test_workflow_workbook_requires_authentication(env):
    http,_,_,_=env
    for guide in ['account','admin','sme','clean-team']:
        response=http.get(f'{BASE}/{guide}/workbook')
        assert response.status_code==401 and not response.content.startswith(b'PK')


@pytest.mark.parametrize('person,guide,allowed',[
    ('root','admin',True),('root','checklists',True),('root','agent-registry',True),('root','sme-profile-approval',True),
    ('root','sme',False),('root','lawyer',False),('root','ddr-runs',False),('root','clean-team',False),
    ('sme','sme',True),('sme','sme-profile-approval',True),('lawyer','lawyer',True),('lawyer','admin',False),('lawyer','sme-profile-approval',False)
])
def test_workflow_workbooks_follow_existing_guide_visibility(env,person,guide,allowed):
    http,_,_,_=env;assert login(http,person).status_code==200
    response=http.get(f'{BASE}/{guide}/workbook')
    if allowed:workbook(response,guide)
    else:assert response.status_code==403 and not response.content.startswith(b'PK')


def test_named_clean_team_membership_is_current_not_an_admin_override(env):
    http,sessions,ids,_=env;assert login(http,'root').status_code==200
    assert http.get(f'{BASE}/clean-team/workbook').status_code==403
    gid=named(sessions,ids,'root')
    workbook(http.get(f'{BASE}/clean-team/workbook'),'clean-team')
    with sessions() as db:db.get(m.CleanTeamMembership,gid).expires_at=clock()-1;db.commit()
    response=http.get(f'{BASE}/clean-team/workbook');assert response.status_code==403 and not response.content.startswith(b'PK')


def test_halden_receives_only_external_clean_team_variant_and_current_links(env):
    _,sessions,ids,app=env;gid=named(sessions,ids,'client')
    with TestClient(app,base_url='https://client.localhost') as http:
        assert login(http,'client',origin='https://client.localhost').status_code==200
        for guide in ['admin','sme','lawyer','ddr-runs','agent-registry','vdr-import']:
            assert http.get(f'{BASE}/{guide}/workbook').status_code==403
        text,links=workbook(http.get(f'{BASE}/clean-team/workbook'),'clean-team')
        assert all(value in text.casefold() for value in ['halden','outside','membership alone','grant'])
        assert not any(marker in text.casefold() for marker in ['sme03','cleanteam01','authorizes analysis'])
        assert any(urlsplit(link).hostname=='client.localhost' and 'Clean' in link for link in links)
        assert not any(urlsplit(link).hostname in {'firm.localhost','admin.localhost'} for link in links)
        with sessions() as db:db.get(m.CleanTeamMembership,gid).revoked=True;db.commit()
        assert http.get(f'{BASE}/clean-team/workbook').status_code==403


def test_clean_team_grant_in_walled_matter_does_not_authorize_workbook(env):
    http,sessions,ids,_=env;named(sessions,ids)
    assert login(http,'lawyer').status_code==200
    workbook(http.get(f'{BASE}/clean-team/workbook'),'clean-team')
    with sessions() as db:db.add(m.EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter']));db.commit()
    assert http.get(f'{BASE}/clean-team/workbook').status_code==403


@pytest.mark.parametrize('person,host',[
    ('root','admin.localhost'),('lawyer','firm.localhost'),('sme','firm.localhost'),
    ('client','client.localhost'),('bank','bank.localhost')
])
def test_each_listed_workflow_is_a_valid_safe_workbook_for_its_audience(env,person,host):
    _,_,_,app=env
    with TestClient(app,base_url='https://'+host) as http:
        assert login(http,person,origin='https://'+host).status_code==200
        response=http.get(BASE);assert response.status_code==200,response.text
        guides=response.json();assert guides
        for guide in guides:
            assert guide['workbook_href']==f"{BASE}/{guide['id']}/workbook"
            assert isinstance(guide['step_count'],int) and guide['step_count']>0
            _,links=workbook(http.get(guide['workbook_href']),guide['id'])
            if person in {'client','bank'}:
                assert {urlsplit(link).hostname for link in links}=={host},'External instructions must use their own portal variant'
        if person=='bank':
            assert not {'admin','sme','lawyer','ddr-runs','agent-registry','clean-team'} & {row['id'] for row in guides}


def test_workbook_is_static_and_excludes_source_person_credentials_and_provider_reads(env,monkeypatch):
    from kestrel.adapters import provider_secrets
    http,sessions,ids,_=env;assert login(http,'lawyer').status_code==200
    person='SYNTHETIC_PERSON_CANARY_41a2';source='SYNTHETIC_SOURCE_CANARY_98fc'
    with sessions() as db:db.get(m.Account,ids['lawyer']).display_name=person;db.commit()
    csrf=login(http,'lawyer').json()['csrf_token']
    response=http.post('/api/v1/workflow/documents',params={'matter_id':ids['matter'],'file_name':'source-canary.txt','logical_key':'WORKBOOK-CANARY','classification':'ordinary','resource_type':'contract','synthetic':True},content=source.encode(),headers={'origin':'https://firm.localhost','x-csrf-token':csrf,'content-type':'application/octet-stream'})
    assert response.status_code==201,response.text
    monkeypatch.setattr(provider_secrets,'configured',lambda *args,**kwargs:pytest.fail('Static workflow downloads must not inspect provider credentials'))
    text,_=workbook(http.get(f'{BASE}/financial/workbook'),'financial')
    for value in [person,source,response.json()['id'],ids['lawyer'],PASSWORD,'KestrelDemo12345!']:
        assert value not in text


def test_unknown_guide_and_hostile_host_never_produce_a_workbook(env):
    http,_,_,_=env;assert login(http,'root').status_code==200
    for guide in ['unknown-guide','%0d%0aX-Evil%3Ayes','%2e%2e%2fprivate']:
        response=http.get(f'{BASE}/{guide}/workbook')
        assert response.status_code in {403,404,422} and not response.content.startswith(b'PK')
    assert http.get(f'{BASE}/admin/workbook',headers={'host':'evil.invalid'}).status_code==403
    text,links=workbook(http.get(f'{BASE}/admin/workbook',headers={'x-forwarded-host':'evil.invalid','forwarded':'host=evil.invalid'}),'admin')
    assert 'evil.invalid' not in text+' '.join(links)


def test_public_workbook_links_use_exact_approved_hosts_not_forwarded_assertions(public_env):
    _,app,_,token=public_env
    with public_client(app,token,'admin.portal.ramijaloudi.com') as http:
        assert public_login(http,'root').status_code==200
        text,links=workbook(http.get(f'{BASE}/admin/workbook',headers={'x-forwarded-host':'evil.invalid','forwarded':'host=evil.invalid'}),'admin',public=True)
        assert any(urlsplit(link).hostname=='admin.portal.ramijaloudi.com' for link in links)
        assert '.localhost' not in text+' '.join(links) and 'evil.invalid' not in text+' '.join(links)
        # "Current" is the authenticated organization, even when a firm account
        # downloads the guide from the permitted Administration shell.
        _,profile_links=workbook(http.get(f'{BASE}/profile/workbook'),'profile',public=True)
        assert {urlsplit(link).hostname for link in profile_links}=={'firm.portal.ramijaloudi.com'}
        assert http.get(f'{BASE}/admin/workbook',headers={'host':'admin.portal.ramijaloudi.com.evil.invalid'}).status_code==403


def test_public_halden_workbook_uses_external_variant_and_halden_navigation(public_env):
    env,app,_,token=public_env;_,sessions,ids,_=env;named(sessions,ids,'client')
    with public_client(app,token,'halden.portal.ramijaloudi.com') as http:
        assert public_login(http,'client').status_code==200
        text,links=workbook(http.get(f'{BASE}/clean-team/workbook'),'clean-team',public=True)
        assert all(value in text.casefold() for value in ['halden','outside','membership alone','grant'])
        assert {urlsplit(link).hostname for link in links}=={'halden.portal.ramijaloudi.com'}
        assert '.localhost' not in text+' '.join(links)
        assert http.get(f'{BASE}/sme/workbook').status_code==403


def test_expired_clean_team_grant_after_initial_visibility_check_withholds_workbook(env,monkeypatch):
    http,sessions,ids,_=env;gid=named(sessions,ids);assert login(http,'lawyer').status_code==200
    original=resources.visible;changed=[]
    def expire(db,actor):
        value=original(db,actor)
        if not changed:
            changed.append(True)
            with sessions() as other:other.get(m.CleanTeamMembership,gid).expires_at=clock()-1;other.commit()
        return value
    monkeypatch.setattr(resources,'visible',expire)
    response=http.get(f'{BASE}/clean-team/workbook')
    assert response.status_code in {403,409} and not response.content.startswith(b'PK')


def test_role_removed_after_initial_visibility_check_withholds_sme_workbook(env,monkeypatch):
    http,sessions,ids,_=env;assert login(http,'sme').status_code==200
    original=resources.visible;changed=[]
    def revoke(db,actor):
        value=original(db,actor)
        if not changed:
            changed.append(True)
            with sessions() as other:other.execute(delete(m.RoleGrant).where(m.RoleGrant.account_id==ids['sme']));other.commit()
        return value
    monkeypatch.setattr(resources,'visible',revoke)
    response=http.get(f'{BASE}/sme/workbook')
    assert response.status_code in {403,409} and not response.content.startswith(b'PK')


@pytest.mark.parametrize('corrupt',['template','catalog'])
def test_tampered_workflow_asset_returns_sanitized_failure_without_workbook(env,tmp_path,monkeypatch,corrupt):
    from kestrel.services import workflow_scripts
    _,_,_,app=env
    original=workflow_scripts.ASSETS
    manifest=json.loads((original/'manifest.json').read_text(encoding='utf-8'))
    filename=manifest['templates']['admin:default']['file']
    isolated=tmp_path/'tampered-workflow-assets';isolated.mkdir()
    for name in ['catalog.json','manifest.json',filename]:
        shutil.copyfile(original/name,isolated/name)
    target=isolated/(filename if corrupt=='template' else 'catalog.json')
    target.write_bytes(target.read_bytes()+(b'UNTRUSTED_WORKFLOW_CANARY_72ca' if corrupt=='template' else b'\n '))
    monkeypatch.setattr(workflow_scripts,'ASSETS',isolated)
    workflow_scripts.catalog.cache_clear()
    try:
        with TestClient(app,base_url='https://firm.localhost',raise_server_exceptions=False) as http:
            assert login(http,'root').status_code==200
            response=http.get(f'{BASE}/admin/workbook')
            assert response.status_code==503 and response.json()['detail']=='Service unavailable'
            assert not response.content.startswith(b'PK') and MIME not in response.headers.get('content-type','')
            assert all(value not in response.text for value in [str(isolated),filename,'UNTRUSTED_WORKFLOW_CANARY_72ca','verification failed'])
    finally:workflow_scripts.catalog.cache_clear()
