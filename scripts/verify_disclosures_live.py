"""Read-only normal-session checks; never proposes, approves or publishes a disclosure."""
import json
from pathlib import Path
from verify_report_connections import Session
ROOT=Path(__file__).resolve().parents[1]
def main():
 values={}
 for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   k,v=line.split('=',1);values[k.strip()]=v.strip().strip('"').strip("'")
 sessions=[];result={};matter='6377dc19-8a25-401a-885e-e6408c23849e'
 try:
  firm=Session('firm.localhost','lawyer01@freshfields.example',values['KESTREL_DUMMY_PASSWORD']);sessions.append(firm)
  status,v=firm.request('GET','/api/v1/disclosures?matter_id='+matter);assert status==200;result['permitted_internal_artifacts']=len(v)
  status,v=firm.request('GET','/openapi/disclosures.json');assert status==200;result['swagger_operations']=sum(len(p) for p in v['paths'].values())
  status,v=firm.request('GET','/api/v1/resources');assert status==200 and any(r['id']=='disclosures' for r in v);result['resources_guide']=True
  for host,user,name in [('admin.localhost','admin01@freshfields.example','admin'),('bank.localhost','bank01@castlegate.example','bank'),('client.localhost','client01@halden.example','client')]:
   s=Session(host,user,values['KESTREL_DUMMY_PASSWORD']);sessions.append(s)
   status,v=s.request('GET','/api/v1/disclosures?matter_id='+matter)
   assert status==(403 if name=='admin' else 200)
   result[name+'_isolation']=True
  (ROOT/'.runtime/prompt-audit/disclosures-live-readonly.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
 finally:
  for s in sessions:s.request('POST','/api/v1/auth/logout',{})
if __name__=='__main__':main()
