import {useEffect,useRef,useState,type FormEvent} from 'react';
import AccountDirectoryDataTable,{type AccountMetadata,type AccountSelection} from './AccountDirectoryDataTable';

type Failure=Error&{status?:number};
async function request(path:string,csrf:string,signal:AbortSignal,body?:unknown,method:'GET'|'PATCH'|'POST'=body===undefined?'GET':'PATCH'):Promise<unknown>{
 const response=await fetch('/api/v1/admin/accounts'+path,{method,cache:'no-store',signal,headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});
 const value=await response.json().catch(()=>null);
 if(!response.ok)throw Object.assign(new Error(typeof value?.detail==='string'?value.detail:'Account request could not be completed.'),{status:response.status});
 if(value===null)throw new Error('The server returned an unreadable account response.');return value;
}
function metadata(value:unknown):AccountMetadata{
 const row=value as Partial<AccountMetadata>|null;
 if(!row||![row.id,row.upn,row.display_name,row.employee_id,row.organization].every(item=>typeof item==='string')||!Array.isArray(row.roles)||row.roles.some(role=>typeof role!=='string')||typeof row.active!=='boolean'||!Number.isInteger(row.revision)||(row.revision||0)<1)throw new Error('The server returned an unverifiable account record.');
 // Keep only the published metadata contract in browser state.
 return {id:row.id!,upn:row.upn!,display_name:row.display_name!,employee_id:row.employee_id!,organization:row.organization!,roles:[...row.roles],active:row.active,revision:row.revision!};
}

export default function AccountManagement({csrf,preview=false}:{csrf:string;preview?:boolean}){
 if(preview)return <section className="card hub-details"><h2>Account names & employee IDs</h2><p>Sign in as an administrator to manage account metadata.</p></section>;
 return <AccountDirectory key={csrf} csrf={csrf}/>;
}

function AccountDirectory({csrf}:{csrf:string}){
 const [selected,setSelected]=useState<AccountSelection|null>(null),[account,setAccount]=useState<AccountMetadata|null>(null),[name,setName]=useState(''),[employee,setEmployee]=useState('');
 const [pendingSelection,setPendingSelection]=useState<AccountSelection|null>(null),[loading,setLoading]=useState(false),[busy,setBusy]=useState(false),[uncertain,setUncertain]=useState(false),[blocked,setBlocked]=useState(false);
 const [error,setError]=useState(''),[notice,setNotice]=useState(''),[refreshKey,setRefreshKey]=useState(0),[detailRefresh,setDetailRefresh]=useState(0),[directoryKey,setDirectoryKey]=useState(0);
 const alive=useRef(true),epoch=useRef(0),busyRef=useRef(false),detailPending=useRef<AbortController|null>(null),verifyPending=useRef<AbortController|null>(null),writePending=useRef<AbortController|null>(null),recoveryPending=useRef<AbortController|null>(null),hydratedSelection=useRef<string|null>(null);
 const dirty=!!account&&(name!==account.display_name||employee!==account.employee_id);
 const selectedRef=useRef(selected);selectedRef.current=selected;
 function clearEditor(){
  epoch.current++;hydratedSelection.current=null;detailPending.current?.abort();verifyPending.current?.abort();recoveryPending.current?.abort();recoveryPending.current=null;setSelected(null);setAccount(null);setName('');setEmployee('');setPendingSelection(null);setLoading(false);setUncertain(false);setNotice('');
 }
 function deny(message='The current session or account-directory authority changed. Reload the permitted directory before continuing.'){
  writePending.current?.abort();busyRef.current=false;setBusy(false);clearEditor();setBlocked(true);setError(message);
 }
 function open(value:AccountSelection){
  if(busyRef.current)return;clearEditor();setError('');setSelected({id:value.id,revision:value.revision});setDetailRefresh(previous=>previous+1);
 }
 function choose(value:AccountSelection){
  if(busyRef.current||uncertain)return;
  if(selected?.id===value.id&&selected.revision===value.revision&&account)return;
  if(dirty){setPendingSelection(value);setNotice('Save or discard the current changes before opening another account.');return;}
  open(value);
 }
 function discard(){
  if(busyRef.current)return;
  if(pendingSelection){open(pendingSelection);return;}
  if(account){setName(account.display_name);setEmployee(account.employee_id);}setNotice('Unsaved metadata changes discarded.');
 }
 async function read(value:AccountSelection,signal:AbortSignal){
  const row=metadata(await request('/'+encodeURIComponent(value.id)+'?revision='+value.revision,csrf,signal));
  if(row.id!==value.id||row.revision!==value.revision)throw Object.assign(new Error('The account version changed. Reload the directory and select its current row.'),{status:409});
  return row;
 }
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;epoch.current++;detailPending.current?.abort();verifyPending.current?.abort();writePending.current?.abort();recoveryPending.current?.abort();};},[]);
 useEffect(()=>{
  if(!selected)return;const key=selected.id+':'+selected.revision;if(hydratedSelection.current===key){hydratedSelection.current=null;return;}const turn=++epoch.current,controller=new AbortController();detailPending.current?.abort();verifyPending.current?.abort();detailPending.current=controller;
  setAccount(null);setName('');setEmployee('');setLoading(true);setUncertain(false);setPendingSelection(null);
  read(selected,controller.signal).then(row=>{if(alive.current&&!controller.signal.aborted&&turn===epoch.current){setAccount(row);setName(row.display_name);setEmployee(row.employee_id);setError('');}}).catch(value=>{
   if(alive.current&&!controller.signal.aborted&&turn===epoch.current){const failure=value as Failure;if([401,403,409].includes(failure.status||0))deny(failure.message);else setError(failure.message);}
  }).finally(()=>{if(detailPending.current===controller){detailPending.current=null;if(alive.current&&turn===epoch.current)setLoading(false);}});
  return()=>controller.abort();
 },[selected?.id,selected?.revision,detailRefresh]);
 useEffect(()=>{
  if(!selected||!account||uncertain)return;const turn=epoch.current;
  const timer=setInterval(()=>{
   if(busyRef.current||detailPending.current||verifyPending.current)return;const controller=new AbortController();verifyPending.current=controller;
   read(selected,controller.signal).then(row=>{
    if(!alive.current||controller.signal.aborted||turn!==epoch.current)return;
    if(row.display_name!==account.display_name||row.employee_id!==account.employee_id){deny('Account metadata changed. Reload the directory before editing its current revision.');return;}
    // Refresh read-only role/state labels; never hydrate over unsaved form text.
    if(row.upn!==account.upn||row.organization!==account.organization||row.active!==account.active||JSON.stringify(row.roles)!==JSON.stringify(account.roles))setAccount(row);
   }).catch(value=>{if(alive.current&&!controller.signal.aborted&&turn===epoch.current)deny((value as Error).message);}).finally(()=>{if(verifyPending.current===controller)verifyPending.current=null;});
  },15000);
  return()=>{clearInterval(timer);verifyPending.current?.abort();};
 },[selected?.id,selected?.revision,account,uncertain]);

 async function save(event:FormEvent){
  event.preventDefault();if(!account||busyRef.current||loading||uncertain||blocked||!dirty)return;
  const target={id:account.id,revision:account.revision},turn=epoch.current,controller=new AbortController();writePending.current=controller;verifyPending.current?.abort();busyRef.current=true;setBusy(true);setError('');setNotice('');setPendingSelection(null);
  try{
   const row=metadata(await request('/'+encodeURIComponent(target.id),csrf,controller.signal,{display_name:name,employee_id:employee,expected_revision:target.revision}));
   if(row.id!==target.id||row.revision!==target.revision+1)throw new Error('The update receipt could not be verified.');
   if(!alive.current||controller.signal.aborted||turn!==epoch.current)return;
   setAccount(row);setName(row.display_name);setEmployee(row.employee_id);setLoading(true);setRefreshKey(previous=>previous+1);setSelected({id:row.id,revision:row.revision});setNotice('Name and employee ID saved. Permissions remain under their separate workflows.');
  }catch(value){
   if(!alive.current||controller.signal.aborted||turn!==epoch.current)return;const failure=value as Failure;
   if([401,403].includes(failure.status||0)){deny(failure.message);return;}
   if(failure.status===409){
    // A duplicate employer ID can also be 409. Preserve the draft only after a
    // fresh read proves the same pinned account and current administrator access.
    try{const checked=await read(target,controller.signal);if(checked.display_name!==account.display_name||checked.employee_id!==account.employee_id)throw new Error('The account metadata changed. Reload the directory.');if(alive.current&&!controller.signal.aborted&&turn===epoch.current)setError(failure.message);}
    catch(check){if(alive.current&&!controller.signal.aborted&&turn===epoch.current)deny((check as Error).message);}
   }else if(failure.status&&failure.status<500)setError(failure.message);
   else{setUncertain(true);setError('The update result is not confirmed. Reload the current account before saving again; no request will be resent automatically.');}
  }finally{if(alive.current&&writePending.current===controller){busyRef.current=false;setBusy(false);writePending.current=null;}}
 }
 async function reloadSelected(){
  if(busyRef.current||!selectedRef.current)return;
  const target=selectedRef.current;
  if(!uncertain){open(target);return;}
  // Resolve the current revision after an unknown PATCH result. This is a bounded
  // Root-only directory read followed by a pinned read, never a write retry.
  const turn=++epoch.current,controller=new AbortController();recoveryPending.current?.abort();detailPending.current?.abort();verifyPending.current?.abort();recoveryPending.current=controller;busyRef.current=true;setBusy(true);setLoading(true);setError('');setNotice('');setAccount(null);setName('');setEmployee('');setPendingSelection(null);
  try{
   const result=await request('/query',csrf,controller.signal,{draw:0,start:0,length:2,sort:'id',direction:'asc',search:'',column_filters:{id:target.id}},'POST') as {data?:unknown[];recordsFiltered?:number}|null;
   if(!result||!Array.isArray(result.data)||result.data.length!==1||result.recordsFiltered!==1)throw Object.assign(new Error('The current account could not be resolved uniquely. Reload the permitted directory.'),{status:409});
   const current=metadata(result.data[0]);
   if(current.id!==target.id)throw Object.assign(new Error('The current account did not match the requested account. Reload the permitted directory.'),{status:409});
   const row=await read({id:current.id,revision:current.revision},controller.signal);
   if(!alive.current||controller.signal.aborted||turn!==epoch.current)return;
   hydratedSelection.current=row.id+':'+row.revision;setSelected({id:row.id,revision:row.revision});setDetailRefresh(previous=>previous+1);setAccount(row);setName(row.display_name);setEmployee(row.employee_id);setUncertain(false);setRefreshKey(previous=>previous+1);setNotice('Current account reloaded; compare its details before further changes');
  }catch(value){
   if(alive.current&&!controller.signal.aborted&&turn===epoch.current){const failure=value as Failure;if([401,403,404,409].includes(failure.status||0))deny(failure.message);else setError('The current account could not be verified. Try the read-only reload again; no update has been resent.');}
  }finally{if(alive.current&&recoveryPending.current===controller){recoveryPending.current=null;busyRef.current=false;setBusy(false);setLoading(false);}}
 }
 const valid=name.trim().length>0&&name.length<=128&&/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(employee)&&employee.length<=40;
 return <section className="card hub-details"><h2>Account names & employee IDs</h2><p>Open an account to edit its name or employer-specific employee ID. Leading zeros are retained. Roles and account state are read-only here.</p>
  {error&&<p className="error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  {blocked?<div role="status"><p>The account directory and editor were cleared.</p><button type="button" onClick={()=>{setBlocked(false);setError('');setDirectoryKey(previous=>previous+1);setRefreshKey(previous=>previous+1);}}>Reload permitted directory</button></div>:<AccountDirectoryDataTable key={directoryKey} csrf={csrf} refreshKey={refreshKey} disabled={busy||uncertain} onChoose={choose} onDenied={()=>deny()}/>}
  {loading&&<p role="status">Checking current administrator access and the selected account revision…</p>}
  {!blocked&&selected&&!loading&&!account&&<button type="button" onClick={()=>void reloadSelected()}>{uncertain?'Resolve current account':'Reload selected account'}</button>}
  {!blocked&&account&&<form onSubmit={save} aria-label="Selected account metadata"><h3>{account.upn}</h3><p>{account.organization} · {account.active?'Active':'Inactive'} · {account.roles.length?account.roles.map(role=>role.replace(/_/g,' ')).join(', '):'No roles'} · profile revision {account.revision}</p><small>This selected account remains open while you page or filter the directory.</small>
   {pendingSelection&&<div role="status"><p>Another account was requested. Save these changes or discard them to open it.</p><button type="button" disabled={busy} onClick={discard}>Discard changes and open requested account</button><button type="button" disabled={busy} onClick={()=>{setPendingSelection(null);setNotice('Continue editing the selected account.');}}>Keep editing</button></div>}
   <fieldset disabled={busy||uncertain} style={{border:0,padding:0,minWidth:0}}><div className="columns"><label>Display name<input value={name} onChange={event=>setName(event.target.value)} required maxLength={128}/></label><label>Employee ID<input value={employee} onChange={event=>setEmployee(event.target.value)} required maxLength={40} pattern="[A-Za-z0-9][A-Za-z0-9._-]*"/></label></div></fieldset>
   <div className="api-links"><button className="primary" disabled={busy||loading||uncertain||!csrf||!dirty||!valid}>Save account details</button>{!uncertain&&<button type="button" disabled={busy||!dirty} onClick={discard}>Discard changes</button>}<button type="button" disabled={busy} onClick={()=>void reloadSelected()}>{uncertain?'Reload current account to confirm result':dirty?'Discard changes and reload account':'Reload selected account'}</button></div>
   <p>Each save uses the loaded profile revision. It does not grant roles, activate an account or change matter access.</p>
  </form>}
 </section>;
}
