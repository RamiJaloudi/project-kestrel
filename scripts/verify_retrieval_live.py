"""Read-only live checks; no provider calls or source/governance mutations."""
import json
from pathlib import Path
from verify_report_connections import Session
ROOT=Path(__file__).resolve().parents[1]
def main():
 values={}
 for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   k,v=line.split('=',1);values[k.strip()]=v.strip().strip('"').strip("'")
 s=Session('firm.localhost','lawyer01@freshfields.example',values['KESTREL_DUMMY_PASSWORD'])
 try:
  status,v=s.request('GET','/openapi/questions.json');assert status==200
  modes=v['components']['schemas']['Ask']['properties']['mode']['enum'];assert set(['automatic','lexical','semantic','hybrid','financial'])<=set(modes)
  status,g=s.request('GET','/api/v1/resources');assert status==200 and any(x['id']=='retrieval' for x in g)
  result={'swagger_modes':modes,'retrieval_resources':True,'provider_calls':0,'governance_mutations':0}
  (ROOT/'.runtime/prompt-audit/retrieval-live-readonly.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
 finally:s.request('POST','/api/v1/auth/logout',{})
if __name__=='__main__':main()
