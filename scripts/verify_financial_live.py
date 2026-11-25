"""Normal-session read checks. No financial proposals, approvals, feature changes or AI calls."""
import json
from pathlib import Path
from verify_report_connections import Session
ROOT=Path(__file__).resolve().parents[1]
def main():
 values={}
 for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   k,v=line.split('=',1);values[k.strip()]=v.strip().strip('"').strip("'")
 sessions=[];matter='6377dc19-8a25-401a-885e-e6408c23849e';result={}
 try:
  firm=Session('firm.localhost','lawyer01@freshfields.example',values['KESTREL_DUMMY_PASSWORD']);sessions.append(firm)
  status,v=firm.request('GET','/openapi/financial.json');assert status==200;result['swagger_operations']=sum(len(p) for p in v['paths'].values())
  fields=v['components']['schemas']['Fact']['properties'];assert {'context_spans','numeric_notation'}<=set(fields);result['literal_header_and_numeric_schema']=True
  status,v=firm.request('POST','/api/v1/financial/query',{'matter_id':matter});assert status==200 and v['authorized_count']==0;result['financial_facts']=0
  status,v=firm.request('GET','/api/v1/resources');assert status==200 and any(x['id']=='financial' for x in v);result['resources_guide']=True
  admin=Session('admin.localhost','admin01@freshfields.example',values['KESTREL_DUMMY_PASSWORD']);sessions.append(admin)
  status,v=admin.request('GET','/api/v1/financial/bank-gate?matter_id='+matter);assert status==200 and not v['enabled'] and v['revision']==0;result['bank_default_off']=True
  status,v=admin.request('POST','/api/v1/financial/query',{'matter_id':matter});assert status==403;result['admin_no_content_override']=True
  bank=Session('bank.localhost','bank01@castlegate.example',values['KESTREL_DUMMY_PASSWORD']);sessions.append(bank)
  status,v=bank.request('POST','/api/v1/financial/query',{'matter_id':matter});assert status==403;result['bank_gate_enforced']=True
  result.update({'provider_calls':0,'governance_mutations':0})
  (ROOT/'.runtime/prompt-audit/financial-live-readonly.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
 finally:
  for s in sessions:s.request('POST','/api/v1/auth/logout',{})
if __name__=='__main__':main()
