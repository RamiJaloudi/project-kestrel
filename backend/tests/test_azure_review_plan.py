"""The offline infrastructure reviewer must not accept public or secret inputs."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'deployment/azure/Review-Plan.ps1'
COMPILER=ROOT/'.runtime/tools/bicep-0.49.2.exe'
pytestmark=pytest.mark.skipif(os.name!='nt' or not shutil.which('powershell.exe') or not COMPILER.is_file(),reason='Offline Windows review requires the separately verified official Bicep compiler')


def review(tmp_path,change=None):
    values=json.loads((ROOT/'deployment/azure/parameters.example.json').read_text(encoding='utf-8'))
    if change:values['parameters'].update(copy.deepcopy(change))
    source=tmp_path/'nonsecret-parameters.json';source.write_text(json.dumps(values),encoding='utf-8')
    target=tmp_path/'receipt.json'
    process=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(SCRIPT),'-ParametersPath',str(source),'-CompilerPath',str(COMPILER),'-OutputPath',str(target)],capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    return process,target


def test_review_compiles_closed_plan_without_cloud_credentials(tmp_path):
    process,target=review(tmp_path)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(target.read_text(encoding='utf-8-sig'))
    assert result['public_web_open'] is False
    assert 'no Azure validation or resource creation' in result['scope']
    assert len(result['hosts'])==5 and result['cost']['base_monthly']==79.66
    template=json.loads((tmp_path/'reviewed-arm.json').read_text(encoding='utf-8-sig'))
    assert template['parameters']['adminPassword']['type']=='securestring'
    assert template['parameters']['allowPublicWeb']['defaultValue'] is False


@pytest.mark.parametrize('change',[
    {'allowPublicWeb':{'value':True}},
    {'allowPublicWeb':{'value':'false'}},
    {'adminPassword':{'value':'DO-NOT-PRINT-THIS-TEST-CREDENTIAL'}},
    {'adminSourceIp':{'value':'0.0.0.0/0'}},
    {'adminSourceIp':{'value':'2130706433'}},
    {'vmSize':{'value':'Standard_D2as_v5'}},
])
def test_review_refuses_unsafe_or_unreviewed_parameters(tmp_path,change):
    process,target=review(tmp_path,change)
    assert process.returncode!=0
    assert not target.exists() and not (tmp_path/'reviewed-arm.json').exists()
    assert 'no cloud action was attempted' in process.stdout
    assert 'DO-NOT-PRINT-THIS-TEST-CREDENTIAL' not in process.stdout+process.stderr
