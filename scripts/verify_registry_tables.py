"""Normal-session, read-only registry checks on LOCAL HTTPS port 8443.

Only sign-in/out bookkeeping and read/query routes are invoked. Never create a
client/matter, assign a person, change a wall, approve content or call a provider.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
B='/api/v1/validation'
ACCESS={'id','account_id','matter_id','username','organization','assigned','blocked','effective_blocked','active'}
HISTORY={'id','matter_id','kind','rationale','actor_id','target_id','occurred_at','revision'}
CONTEXT={'matter_id','matter_name','client_id','client_name','client_number','matter_number','client_matter_number','validation_status','revision'}
TARGET={'account_id','username','organization','assigned','blocked','effective_blocked','active','matter_revision'}


def require(condition,message):
    if not condition:raise RuntimeError(message)


def collect(session,dataset,payload,revision,bound):
    rows=[];total=None
    for offset in range(0,bound+1,50):
        status,page=session.request('POST',B+'/tables/'+dataset+'/query',{**payload,'start':offset,'length':50})
        require(status==200,'Registry query unavailable, denied or changed; activate the frozen build and retry')
        require(page['matter_revision']==revision,'Registry revision changed during verification; retry read-only checks')
        require(page['recordsTotal']==page['recordsFiltered'] and page['recordsTotal']<=bound,'Local verifier bound exceeded or unexpected baseline filtering')
        if total is None:total=page['recordsTotal']
        require(page['recordsTotal']==total,'Registry count changed during verification; retry')
        require(all(row['matter_id']==payload['matter_id'] for row in page['data']),'Registry response scope mismatch')
        rows.extend(page['data'])
        if len(rows)>=total:break
        require(len(page['data'])==50,'Incomplete registry page')
    require(len(rows)==total and len({row['id'] for row in rows})==total,'Registry paging omitted or duplicated records')
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matter',help='Permitted matter UUID; default is synthetic primary 012345-789012')
    parser.add_argument('--max-rows',type=int,default=1000,metavar='N',help='Bounded local verification ceiling, 1 through 1000')
    options=parser.parse_args()
    if not 1<=options.max_rows<=1000:parser.error('--max-rows must be between 1 and 1000')
    from kestrel.localenv import read_env
    from verify_report_connections import Session
    sessions=[]
    try:
        password=read_env()['KESTREL_DUMMY_PASSWORD']
        root=Session('admin.localhost','admin01@freshfields.example',password);sessions.append(root)
        status,matters=root.request('GET',B+'/matters');require(status==200,'Root registry list unavailable')
        selected=next((row for row in matters if row['matter_id']==options.matter),None) if options.matter else next((row for row in matters if row['client_matter_number']=='012345-789012'),None)
        require(selected is not None,'Requested permitted synthetic matter is unavailable')
        matter=selected['matter_id'];revision=selected['revision'];base=B+'/matters/'+matter
        status,legacy_access=root.request('GET',base+'/access');require(status==200,'Legacy access read unavailable')
        status,legacy_history=root.request('GET',base+'/history');require(status==200,'Legacy history read unavailable')
        access_payload={'matter_id':matter,'draw':7,'sort':'username','direction':'asc'}
        history_payload={'matter_id':matter,'draw':8,'sort':'revision','direction':'desc'}
        access=collect(root,'access',access_payload,revision,options.max_rows)
        history=collect(root,'history',history_payload,revision,options.max_rows)
        require(all(set(row)==ACCESS and row['id']==row['account_id'] and all(isinstance(row[key],bool) for key in ['assigned','blocked','effective_blocked','active']) for row in access),'Access metadata contract mismatch')
        require(all(set(row)==HISTORY and row['kind'].startswith(('matter.','access.')) for row in history),'History metadata contract mismatch')
        require(access==sorted(access,key=lambda row:(row['username'].casefold(),row['id'])),'Access order/tie mismatch')
        require(history==sorted(history,key=lambda row:(-row['revision'],row['id'])),'History order/tie mismatch')
        legacy_by_id={row['account_id']:row for row in legacy_access}
        require(set(legacy_by_id)=={row['id'] for row in access},'Legacy/new participant count or identity mismatch')
        for row in access:
            old=legacy_by_id[row['id']]
            require(all(row[key]==(bool(old[key]) if key in {'assigned','blocked','effective_blocked'} else old[key]) for key in old),'Legacy/new participant projection mismatch')
        old_fields={'kind','rationale','actor_id','target_id','occurred_at','revision'}
        signature=lambda row:json.dumps({key:row[key] for key in old_fields},sort_keys=True)
        require(Counter(map(signature,legacy_history))==Counter(map(signature,history)),'Legacy/new decision history mismatch')
        for dataset,payload,rows in [('access',access_payload,access),('history',history_payload,history)]:
            for offset in [0,1]:
                status,page=root.request('POST',B+'/tables/'+dataset+'/query',{**payload,'length':1,'start':offset})
                require(status==200 and page['data']==rows[offset:offset+1] and page['recordsTotal']==len(rows),'Exact one-row page mismatch')
            status,empty=root.request('POST',B+'/tables/'+dataset+'/query',{**payload,'search':'absent-registry-verifier-e7504f'})
            require(status==200 and empty['recordsTotal']==len(rows) and empty['recordsFiltered']==0 and empty['data']==[],'Literal empty-search mismatch')
            for extra in [{'length':51},{'draw':True},{'sort':'password_hash'},{'source_filters':{}},{'saved_view_id':'unsupported'},{'selected_ids':['unsupported']}]:
                status,_=root.request('POST',B+'/tables/'+dataset+'/query',{**payload,**extra})
                require(status==422,'Strict registry query rejection failed')
        status,context=root.request('GET',base+'/context?'+urlencode({'revision':revision}))
        require(status==200 and set(context)==CONTEXT and context==selected,'Pinned matter context differs from current registry metadata')
        for suffix in ['/context','/access-target']:
            params={'revision':revision+1,'username':access[0]['username'] if access else 'unavailable'}
            status,_=root.request('GET',base+suffix+'?'+urlencode(params));require(status==409,'Stale registry pin was not refused')
        target_checked=False
        if access:
            row=access[0]
            status,target=root.request('GET',base+'/access-target?'+urlencode({'revision':revision,'username':row['username']}))
            require(status==200 and set(target)==TARGET and target['matter_revision']==revision,'Pinned target metadata contract mismatch')
            require(all(target[key]==row[key] for key in TARGET-{'matter_revision'}),'Pinned target differs from access grid')
            status,filtered=root.request('POST',B+'/tables/access/query',{**access_payload,'column_filters':{'account_id':row['account_id']}})
            require(status==200 and filtered['recordsFiltered']==1 and filtered['data']==[row],'Exact account column filter mismatch')
            target_checked=True
        for host,user in [('firm.localhost','sme01@freshfields.example'),('client.localhost','client01@halden.example'),('bank.localhost','bank01@castlegate.example')]:
            session=Session(host,user,password);sessions.append(session)
            for dataset in ['access','history']:
                status,denied=session.request('POST',B+'/tables/'+dataset+'/query',{'matter_id':matter})
                require(status==403 and 'recordsTotal' not in denied and 'data' not in denied,'Non-Root registry metadata disclosure')
            for suffix in ['/context','/access-target']:
                status,denied=session.request('GET',base+suffix+'?'+urlencode({'revision':revision,'username':access[0]['username'] if access else 'unavailable'}))
                require(status==403 and 'username' not in denied and 'matter_name' not in denied,'Non-Root pinned metadata disclosure')
        for dataset in ['inventory','financial']:
            status,denied=root.request('POST','/api/v1/tables/'+dataset+'/query',{'matter_id':matter})
            require(status==403 and 'recordsTotal' not in denied,'Root acquired legal-source table access')
        report={'verified':True,'checked_at':int(time.time()),'access_total':len(access),'history_total':len(history),'matter_revision':revision,
            'legacy_counts_and_values_match':True,'stable_pages':True,'real_history_ids_checked':bool(history),'pinned_context':True,'pinned_target':target_checked,
            'stale_pins_refused':True,'strict_queries':True,'non_root_denied':True,'root_has_no_source_override':True,
            'registry_writes':0,'identity_writes':0,'legal_decisions':0,'provider_calls':0,'normal_session_bookkeeping':True}
        (ROOT/'.runtime'/'registry-tables-live-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps(report))
    finally:
        for session in sessions:
            status,_=session.request('POST','/api/v1/auth/logout',{})
            require(status==204,'Verifier session logout failed')


if __name__=='__main__':main()
