"""Read-only live API checks. Normal login; no AI calls or business decisions."""
import http.client,json,ssl
from http.cookies import SimpleCookie
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONTEXT=ssl.create_default_context(cafile=str(ROOT/'.runtime/local-ca.pem'))
class Session:
    def __init__(self,host,user,password):
        self.host=host;self.cookie=''
        code,result=self.request('POST','/api/v1/auth/login',{'username':user,'password':password})
        if code!=200:raise RuntimeError('Normal demo sign-in failed')
        self.csrf=result['csrf_token']
    def request(self,method,path,body=None):
        connection=http.client.HTTPSConnection('localhost',8443,context=CONTEXT,timeout=15)
        headers={'Host':self.host+':8443','Origin':'https://'+self.host+':8443','Content-Type':'application/json'}
        if self.cookie:headers['Cookie']=self.cookie
        if hasattr(self,'csrf'):headers['X-CSRF-Token']=self.csrf
        connection.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers)
        response=connection.getresponse();raw=response.read()
        cookies=SimpleCookie()
        for key,value in response.getheaders():
            if key.lower()=='set-cookie':cookies.load(value)
        if cookies:self.cookie='; '.join(k+'='+v.value for k,v in cookies.items())
        status=response.status;connection.close()
        return status,json.loads(raw) if raw else None

def main():
    values={}
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1);values[key.strip()]=value.strip().strip('"').strip("'")
    password=values.get('KESTREL_DUMMY_PASSWORD')
    if not password:raise RuntimeError('Local synthetic account password is not configured')
    firm=Session('firm.localhost','sme01@freshfields.example',password)
    status,matters=firm.request('GET','/api/v1/workflow/matters');assert status==200
    matter=next(m['id'] for m in matters if m['client_number']=='012345')
    status,internal=firm.request('GET','/api/v1/reports?matter_id='+matter);assert status==200
    for report in internal:
        assert len(report['section_findings'])==len(report['body']['sections'])
        assert all(f['review_state']=='reviewed' for f in report['section_findings'])
    counts={'internal_reports':len(internal)}
    audiences={}
    for host,user,audience in [('client.localhost','client01@halden.example','halden'),('bank.localhost','bank01@castlegate.example','castlegate')]:
        session=Session(host,user,password)
        status,reports=session.request('GET','/api/v1/reports?matter_id='+matter);assert status==200
        for report in reports:
            assert report['released'] and report['audience']==audience
            assert 'section_findings' not in report and 'citations' not in report and 'previous_id' not in report
            if report['body']['sections']:
                status,_=session.request('GET','/api/v1/collaboration?release_id='+report['release_id']+'&section_index=0');assert status==200
        counts[audience+'_reports']=len(reports);audiences[audience]=(session,reports)
    if audiences['halden'][1]:
        status,_=audiences['castlegate'][0].request('GET','/api/v1/collaboration?release_id='+audiences['halden'][1][0]['release_id']+'&section_index=0')
        assert status==403
        counts['cross_audience_denied']=True
    for session in [firm,*[value[0] for value in audiences.values()]]:
        status,_=session.request('POST','/api/v1/auth/logout',{});assert status==204
    print(json.dumps({'verified':True,**counts,'paid_calls':0,'business_decisions':0}))
if __name__=='__main__':main()
