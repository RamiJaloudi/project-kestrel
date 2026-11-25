import {useEffect,useRef,useState} from 'react';

export type SavedTableQuery={matter_id:string;draw?:number;start?:number;length?:number;sort?:string|null;direction?:'asc'|'desc';search?:string;column_filters?:Record<string,string>;source_filters?:Record<string,unknown>|null;financial_filters?:Record<string,unknown>|null;task_filters?:Record<string,unknown>|null;finding_filters?:Record<string,unknown>|null;saved_view_id?:string|null;saved_view_version_hash?:string|null};
type EvidenceRef={kind:'source'|'financial';id:string};
export type SavedTableConfiguration={id:string;matter_id:string;dataset:'inventory'|'financial';owner_id:string;is_owner:boolean;version_id:string;revision:number;version_hash:string;name:string;query:SavedTableQuery;handling:'private_unclassified'|'source_bound';evidence_refs:EvidenceRef[];shared:boolean;share_requests:ShareRequest[]};
type ShareRequest={id:string;view_id:string;version_hash:string;content_hash:string;recipient_ids:string[];expires_at:number;state:string;rationale:string;can_review:boolean;is_owner:boolean;configuration:SavedTableConfiguration;decisions:{operation:string;actor_id:string;rationale:string;content_reviewed:boolean}[]};
type Identity={organization:string;roles:string[]};
type Failure=Error&{status?:number};
const ROOT='/api/v1/table-views';

export default function SavedTableViews({matter,dataset,csrf,internal,selected,getQuery,onLoad,onClear,onDenied}:{matter:string;dataset:'inventory'|'financial';csrf:string;internal:boolean;selected:string[];getQuery:()=>SavedTableQuery;onLoad:(value:SavedTableConfiguration)=>void;onClear:()=>void;onDenied:()=>void}){
 const [expanded,setExpanded]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [identity,setIdentity]=useState<Identity|null>(null),[available,setAvailable]=useState(true),[rows,setRows]=useState<SavedTableConfiguration[]>([]),[queue,setQueue]=useState<ShareRequest[]>([]),[people,setPeople]=useState<{id:string;name:string}[]>([]);
 const [choice,setChoice]=useState(''),[current,setCurrent]=useState<SavedTableConfiguration|null>(null),[name,setName]=useState(''),[rationale,setRationale]=useState(''),[handling,setHandling]=useState<'private_unclassified'|'source_bound'>(internal?'private_unclassified':'source_bound'),[reuseBindings,setReuseBindings]=useState(false);
 const [recipients,setRecipients]=useState<string[]>([]),[days,setDays]=useState(7),[shareReason,setShareReason]=useState(''),[decisionReason,setDecisionReason]=useState(''),[reviewed,setReviewed]=useState<Record<string,boolean>>({});
 const mounted=useRef(true),epoch=useRef(0),controllers=useRef(new Set<AbortController>()),busyRef=useRef(false),scope=useRef('');
 const scopeKey=matter+':'+dataset+':'+csrf;scope.current=scopeKey;
 function clearPrivate(){setRows([]);setQueue([]);setPeople([]);setCurrent(null);setChoice('');setName('');setRationale('');setShareReason('');setDecisionReason('');setRecipients([]);setReviewed({});setReuseBindings(false);}
 function handleError(value:unknown){const failure=value as Failure;if(failure.name==='AbortError'||!mounted.current)return;setError(failure.message);if(failure.status&&[401,403,409].includes(failure.status)){clearPrivate();onDenied();}}
 async function api<T,>(path:string,body?:unknown):Promise<T>{
  const controller=new AbortController(),generation=epoch.current,key=scopeKey;controllers.current.add(controller);
  try{const response=await fetch(path,{method:body===undefined?'GET':'POST',cache:'no-store',signal:controller.signal,headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});const value=await response.json().catch(()=>null);
   if(!mounted.current||generation!==epoch.current||scope.current!==key)throw new DOMException('Stale saved-query response','AbortError');
   if(!response.ok)throw Object.assign(new Error(typeof value?.detail==='string'?value.detail:'Saved query request denied; check its fields and current permissions.'),{status:response.status});if(value===null)throw new Error('Saved query returned an unreadable response.');return value as T;
  }finally{controllers.current.delete(controller);}
 }
 async function refresh(){
  const who=await api<Identity>('/api/v1/auth/me');setIdentity(who);
  if(who.organization!=='firm'&&(who.organization!=='castlegate'||dataset!=='financial')){clearPrivate();setAvailable(false);return;}
  setAvailable(true);const query='?'+new URLSearchParams({matter_id:matter,dataset});
  const [configs,names,requests]=await Promise.all([api<SavedTableConfiguration[]>(ROOT+query),internal?api<{id:string;name:string}[]>(ROOT+'/recipients'+query):Promise.resolve([]),internal?api<ShareRequest[]>(ROOT+'/share-requests'+query):Promise.resolve([])]);
  setRows(configs);setPeople(names);setQueue(requests);
  setCurrent(previous=>previous?configs.find(v=>v.id===previous.id)||null:null);
 }
 async function act(work:()=>Promise<void>){if(busyRef.current)return;busyRef.current=true;setBusy(true);setError('');setNotice('');const generation=epoch.current;try{await work();}catch(value){if(generation===epoch.current)handleError(value);}finally{if(mounted.current&&generation===epoch.current){busyRef.current=false;setBusy(false);}}}
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;epoch.current++;controllers.current.forEach(c=>c.abort());controllers.current.clear();};},[]);
 useEffect(()=>{epoch.current++;controllers.current.forEach(c=>c.abort());busyRef.current=false;setBusy(false);clearPrivate();setIdentity(null);setError('');setNotice('');setAvailable(true);},[matter,dataset,csrf]);
 useEffect(()=>{if(!expanded)return;void act(refresh);const timer=setInterval(()=>void act(refresh),30000);return()=>clearInterval(timer);},[expanded,matter,dataset,csrf]);
 const bindings:EvidenceRef[]=reuseBindings&&current?current.evidence_refs:selected.map(id=>({kind:dataset==='inventory'?'source':'financial',id}));
 const canSave=name.trim().length>0&&rationale.trim().length>=10&&(handling!=='source_bound'||bindings.length>0&&bindings.length<=50);
 function adopt(value:SavedTableConfiguration){onLoad(value);setCurrent(value);setChoice(value.id);setName(value.name);setHandling(value.handling);setReuseBindings(false);setRecipients([]);setReviewed({});}
 async function save(revision=false){
  const raw=getQuery(),query={...raw,draw:0,start:0};delete query.saved_view_id;delete query.saved_view_version_hash;
  const body={name:name.trim(),query,handling,evidence_refs:handling==='source_bound'?bindings:[],rationale:rationale.trim(),request_key:crypto.randomUUID()};
  const value=revision&&current?await api<SavedTableConfiguration>(ROOT+'/'+encodeURIComponent(current.id)+'/versions',{...body,expected_version_hash:current.version_hash}):await api<SavedTableConfiguration>(ROOT,{...body,matter_id:matter,dataset});
  adopt(value);setRationale('');await refresh();setNotice(revision?'Saved a new immutable revision. Earlier revisions and sharing decisions remain separate.':'Saved a private query. Sharing requires an independent review.');
 }
 async function share(){if(!current)return;await api<ShareRequest>(ROOT+'/'+encodeURIComponent(current.id)+'/share-requests',{version_hash:current.version_hash,recipient_ids:recipients,expires_in_days:days,rationale:shareReason.trim(),request_key:crypto.randomUUID()});setShareReason('');setRecipients([]);await refresh();setNotice('Named sharing request submitted. No approval or release was performed.');}
 async function decide(request:ShareRequest,operation:'approve'|'reject'|'revoke'){await api(ROOT+'/share-requests/'+encodeURIComponent(request.id)+'/decisions',{operation,content_hash:request.content_hash,content_reviewed:reviewed[request.id]===true,rationale:decisionReason.trim()});setDecisionReason('');setReviewed({});await refresh();setNotice('Recorded '+operation+' for the exact sharing request.');}
 const requests=[...new Map([...rows.flatMap(v=>v.share_requests||[]),...queue].map(v=>[v.id,v])).values()];
 return <details className="card saved-table-views" open={expanded} onToggle={event=>setExpanded(event.currentTarget.open)}><summary>Saved table queries</summary>
  {error&&<p className="error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  {!available?<p>Saved queries are unavailable for this audience.</p>:<>
   <p>Names and filter text can contain confidential information. New saves are private. Each load checks current access; hiding columns never changes permissions.</p>
   <div className="table-tools"><label>Permitted saved query<select disabled={busy} value={choice} onChange={event=>setChoice(event.target.value)}><option value="">Choose a private or approved shared query</option>{rows.map(v=><option key={v.id} value={v.id}>{v.name} · revision {v.revision}{v.shared?' · shared':' · private'}</option>)}</select></label><button disabled={busy||!choice} onClick={()=>void act(async()=>{adopt(await api<SavedTableConfiguration>(ROOT+'/'+encodeURIComponent(choice)));setNotice('Loaded the current permitted saved query. Editing searches, sort or page size detaches its saved identity.');})}>Load query</button><button disabled={busy} onClick={()=>{onClear();setCurrent(null);setChoice('');setNotice('Returned to the current workspace filters.');}}>Use workspace filters</button><button disabled={busy} onClick={()=>void act(refresh)}>Refresh permissions</button></div>
   <div className="source-work-columns"><label>Private saved-query name<input maxLength={96} value={name} onChange={event=>setName(event.target.value)}/></label><label>Handling<select disabled={!internal} value={handling} onChange={event=>setHandling(event.target.value as typeof handling)}>{internal&&<option value="private_unclassified">Private text, unclassified</option>}<option value="source_bound">Bind to selected evidence</option></select></label></div>
   {handling==='source_bound'&&<p>{bindings.length} evidence bindings (1–50 required). Select confirmed inventory sources or currently permitted financial facts in the table. {current?.evidence_refs.length? <label><input type="checkbox" checked={reuseBindings} onChange={event=>setReuseBindings(event.target.checked)}/>Use the loaded revision’s {current.evidence_refs.length} existing evidence bindings</label>:null}</p>}
   <label>Save / revision rationale<textarea value={rationale} maxLength={1000} onChange={event=>setRationale(event.target.value)} placeholder="Explain the query and its evidence bindings (at least 10 characters)"/></label>
   <div className="table-tools"><button disabled={busy||!canSave} onClick={()=>void act(()=>save())}>Save new private query</button><button disabled={busy||!canSave||!current?.is_owner} onClick={()=>void act(()=>save(true))}>Append private revision</button>{current&&<small>Loaded revision {current.revision}{current.shared?' · approved named share':' · owner only'}. Column visibility is a live display preference.</small>}</div>
   {internal&&<details><summary>Named sharing and independent review</summary><p>Only an evidence-bound revision can be shared internally. A source-cleared SME who is neither owner nor recipient must review all saved text and bindings. No external sharing is available here.</p>
    {current?.is_owner&&current.handling==='source_bound'&&<><label>Named firm recipients (maximum 25)<select multiple value={recipients} onChange={event=>setRecipients(Array.from(event.target.selectedOptions).map(v=>v.value).slice(0,25))}>{people.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Expires in days<input type="number" min={1} max={30} value={days} onChange={event=>setDays(Number(event.target.value))}/></label><label>Sharing rationale<textarea maxLength={1000} value={shareReason} onChange={event=>setShareReason(event.target.value)}/></label><button disabled={busy||!recipients.length||days<1||days>30||!Number.isInteger(days)||shareReason.trim().length<10} onClick={()=>void act(share)}>Request independent named sharing</button></>}
    <label>Decision / revocation rationale<textarea maxLength={1000} value={decisionReason} onChange={event=>setDecisionReason(event.target.value)}/></label>
    {!requests.length&&<p>No permitted sharing requests. SME review requests appear here after refreshing permissions.</p>}
    {requests.map(request=><article className="card" key={request.id}><b>{request.configuration.name} · {request.state}</b><p>Expires {new Date(request.expires_at*1000).toLocaleString()} · recipients: {request.recipient_ids.map(id=>people.find(p=>p.id===id)?.name||id).join(', ')}</p><p>{request.rationale}</p><details><summary>Inspect exact saved query and evidence</summary><pre className="json-editor">{JSON.stringify({name:request.configuration.name,revision:request.configuration.revision,query:request.configuration.query,handling:request.configuration.handling,evidence_refs:request.configuration.evidence_refs,version_hash:request.version_hash,sharing_hash:request.content_hash},null,2)}</pre></details>
     {request.can_review&&request.state==='pending'&&<><label><input type="checkbox" checked={reviewed[request.id]===true} onChange={event=>setReviewed({...reviewed,[request.id]:event.target.checked})}/>I reviewed this exact saved name, query/filter text, evidence bindings and sharing rationale.</label><button disabled={busy||!reviewed[request.id]||decisionReason.trim().length<10} onClick={()=>void act(()=>decide(request,'approve'))}>Approve exact named share</button><button disabled={busy||decisionReason.trim().length<10} onClick={()=>void act(()=>decide(request,'reject'))}>Reject request</button></>}
     {(request.is_owner||identity?.roles.includes('legal_sme'))&&!['revoked','rejected'].includes(request.state)&&<button disabled={busy||decisionReason.trim().length<10} onClick={()=>void act(()=>decide(request,'revoke'))}>Revoke future sharing</button>}
     {!!request.decisions.length&&<details><summary>Retained decisions</summary>{request.decisions.map((d,index)=><p key={index}>{d.operation} · {d.rationale}</p>)}</details>}
    </article>)}
   </details>}
  </>}
 </details>;
}
