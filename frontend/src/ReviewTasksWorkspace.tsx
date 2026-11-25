import {useEffect,useRef,useState} from 'react';
import KestrelDataTable,{type TableColumn} from './KestrelDataTable';
import DocumentReader,{type ReaderTarget} from './DocumentReader';
import {useMatterSelection,selectPermittedMatter} from './matterSelection';
import {workflowLink} from './WorkflowSteps';

type Identity={id:string;organization:string;roles:string[]};
type Matter={id:string;name:string;client_number:string;matter_number:string};
type TaskRow={id:string;matter_id:string;source_id:string;document_id:string;logical_key:string;file_name:string;stage:string;status:string;revision:number;assignee_name:string|null;created_by_name:string|null;due_at:number|null;last_activity_at:number;historical:boolean;can_reassign:boolean};
type Person={id:string;name:string;upn:string};
type Command={matter_id:string;items:{id:string;expected_revision:number}[];assignee_id:string;rationale:string;request_key:string};
type Receipt={requested:number;succeeded:number;unavailable:number};
type Failure=Error&{status?:number};
const stages:Record<string,string>={review:'Document review',qc:'Quality control',specialized_legal:'Specialist legal',financial:'Financial review',ai_coordination:'AI coordination'};
const statuses=['assigned','accepted','in_progress','paused','completed','cancelled'];
const label=(value:string)=>value.replace(/_/g,' ');
const utc=(value:number|null)=>value===null?'Not set':new Date(value*1000).toISOString().replace('T',' ').replace('.000Z',' UTC');

async function request<T,>(path:string,csrf:string,signal:AbortSignal,body?:unknown):Promise<T>{
 const response=await fetch('/api/v1/'+path,{method:body===undefined?'GET':'POST',cache:'no-store',signal,headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});
 const value=await response.json().catch(()=>null);
 if(!response.ok)throw Object.assign(new Error(typeof value?.detail==='string'?value.detail:'The request could not be completed.'),{status:response.status});
 if(value===null)throw new Error('The server returned an unreadable response.');
 return value as T;
}

export default function ReviewTasksWorkspace({csrf,identity}:{csrf:string;identity:Identity}){
 const [matters,setMatters]=useState<Matter[]>([]),[matter,setMatter]=useMatterSelection(),[error,setError]=useState('');
 const permitted=identity.organization==='firm'&&identity.roles.some(r=>['firm_lawyer','legal_sme','antitrust_counsel'].includes(r));
 useEffect(()=>{
  if(!permitted)return;
  const controller=new AbortController();
  request<Matter[]>('workflow/matters',csrf,controller.signal).then(rows=>{setMatters(rows);setMatter(selectPermittedMatter(rows));}).catch(e=>{if(!controller.signal.aborted){setMatters([]);setMatter('');setError(e.message);}});
  return()=>controller.abort();
 },[csrf,permitted]);
 if(!permitted)return <section className="card"><h2>Tasks & assignments</h2><p>A permitted firm legal account is required.</p></section>;
 return <><section className="card task-workspace-heading"><div><h2>Tasks & assignments</h2><p>Find review work, open its evidence and manage assignments across the matter.</p></div><label>Matter<select value={matter} onChange={e=>setMatter(e.target.value)}><option value="">Choose a permitted matter</option>{matters.map(m=><option value={m.id} key={m.id}>{m.client_number}-{m.matter_number} · {m.name}</option>)}</select></label>{error&&<p className="error" role="alert">{error}</p>}</section>{matter&&<TaskGrid key={matter+':'+csrf} matter={matter} csrf={csrf} identity={identity}/>}</>;
}

function TaskGrid({matter,csrf,identity}:{matter:string;csrf:string;identity:Identity}){
 const [status,setStatus]=useState(''),[stage,setStage]=useState(''),[mine,setMine]=useState(false),[created,setCreated]=useState(false),[historical,setHistorical]=useState(false);
 const [selected,setSelected]=useState<TaskRow[]>([]),[people,setPeople]=useState<Person[]>([]),[assignee,setAssignee]=useState(''),[rationale,setRationale]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState(''),[pending,setPending]=useState<Command|null>(null),[refresh,setRefresh]=useState(0),[reader,setReader]=useState<ReaderTarget|null>(null);
 const alive=useRef(true),busyRef=useRef(false),operation=useRef<AbortController|null>(null),picker=useRef<AbortController|null>(null);
 const signature=JSON.stringify(selected.map(r=>[r.id,r.revision]).sort()),currentSignature=useRef(signature);currentSignature.current=signature;
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;operation.current?.abort();picker.current?.abort();};},[]);
 useEffect(()=>{picker.current?.abort();setPeople([]);setAssignee('');},[signature]);
 function deny(){picker.current?.abort();operation.current?.abort();busyRef.current=false;setBusy(false);setPeople([]);setAssignee('');setSelected([]);setReader(null);setRationale('');setPending(null);setMessage('');setError('The current session or access changed. Refresh the workspace before continuing.');}
 async function eligible(){
  if(busyRef.current)return;busyRef.current=true;
  picker.current?.abort();const controller=new AbortController();picker.current=controller;const captured=signature;
  setBusy(true);setError('');setMessage('');setPeople([]);setAssignee('');
  try{const rows=await request<Person[]>('tables/tasks/eligible-people',csrf,controller.signal,{matter_id:matter,items:selected.map(r=>({id:r.id,expected_revision:r.revision}))});if(alive.current&&!controller.signal.aborted&&captured===currentSignature.current){setPeople(rows);if(!rows.length)setMessage('No other person is currently eligible for every selected task and its retained history.');}}
  catch(value){if(alive.current&&!controller.signal.aborted){const failure=value as Failure;setError(failure.message);if([401,403].includes(failure.status||0))deny();}}
  finally{if(alive.current&&picker.current===controller){busyRef.current=false;setBusy(false);}}
 }
 async function submit(command:Command,retry=false){
  if(busyRef.current)return;busyRef.current=true;
  const controller=new AbortController();operation.current=controller;setPending(command);setBusy(true);setError('');setMessage('');
  try{const receipt=await request<Receipt>('tables/tasks/bulk-reassign',csrf,controller.signal,command);if(!alive.current||controller.signal.aborted)return;
   if(![receipt.requested,receipt.succeeded,receipt.unavailable].every(v=>Number.isInteger(v)&&v>=0)||receipt.requested!==command.items.length||receipt.succeeded+receipt.unavailable!==receipt.requested)throw new Error('Unverifiable reassignment receipt');
   setPending(null);setPeople([]);setAssignee('');setRationale('');setSelected([]);setRefresh(v=>v+1);
   setMessage(`${receipt.succeeded} of ${receipt.requested} tasks reassigned or already recorded; ${receipt.unavailable} unavailable. Open source work to inspect the retained history. No findings were approved or released.`);
  }catch(value){if(alive.current&&!controller.signal.aborted){const failure=value as Failure;
   if(failure.status&&failure.status<500&&(!retry||[401,403].includes(failure.status))){setPending(null);setSelected([]);setRefresh(v=>v+1);setError(failure.message);if([401,403].includes(failure.status))deny();}
   else setError('The result is unknown. Inspect source work or retry the exact same request below; successful rows will not be reassigned twice.');
  }}finally{if(alive.current&&operation.current===controller){busyRef.current=false;setBusy(false);}}
 }
 const columns:TableColumn<TaskRow>[]=[
  {key:'file_name',title:'Document',render:r=><><b>{r.file_name}</b><small>{r.logical_key}{r.historical?' · historical':''} · task {r.id.slice(0,8)} · r{r.revision}</small></>},
  {key:'stage',title:'Stage',render:r=>stages[r.stage]||label(r.stage)},
  {key:'status',title:'Status',render:r=><span className="tag">{label(r.status)}</span>},
  {key:'assignee_name',title:'Assigned to',render:r=>r.assignee_name||'Unavailable'},
  {key:'created_by_name',title:'Assigned by',render:r=>r.created_by_name||'Unavailable'},
  {key:'due_at',title:'Due (UTC)',render:r=>utc(r.due_at)},
  {key:'last_activity_at',title:'Last activity (UTC)',render:r=>utc(r.last_activity_at)},
  {key:'id',title:'Evidence / task actions',orderable:false,searchable:false,render:r=><div className="api-links"><button onClick={()=>setReader({id:r.source_id,historical:r.historical})}>Read evidence</button><a href={workflowLink('Documents',matter,r.source_id,undefined,undefined,undefined,r.historical)}>Manage source work</a></div>}
 ];
 const selectionReady=selected.length>0&&selected.length<=25&&selected.every(r=>r.can_reassign);
 return <section className="card task-workspace">
  <div className="task-filters"><label>Status<select disabled={busy||!!pending} value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{statuses.map(s=><option key={s} value={s}>{label(s)}</option>)}</select></label><label>Stage<select disabled={busy||!!pending} value={stage} onChange={e=>setStage(e.target.value)}><option value="">All stages</option>{Object.entries(stages).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label><label><input type="checkbox" disabled={busy||!!pending} checked={mine} onChange={e=>setMine(e.target.checked)}/>Assigned to me</label><label><input type="checkbox" disabled={busy||!!pending} checked={created} onChange={e=>setCreated(e.target.checked)}/>Created by me</label><label><input type="checkbox" disabled={busy||!!pending} checked={historical} onChange={e=>setHistorical(e.target.checked)}/>Include permitted historical sources</label><button disabled={busy} onClick={()=>setRefresh(v=>v+1)}>Refresh tasks</button></div>
  <details className="task-bulk" open={selected.length>0||!!pending}><summary>Reassign selected tasks · {selected.length} selected</summary><p>Select up to 25 current tasks you created, or manage as a scoped Legal SME. The new assignee must be eligible for every selected task and all its retained restrictions. Completed and frozen work cannot be reassigned here.</p>
   {pending?<div role="status"><p>A saved request for {pending.items.length} tasks needs a confirmed result. Retry preserves its original revisions, target and request ID.</p><button className="primary" disabled={busy} onClick={()=>void submit(pending,true)}>Retry same request</button><p><a href={workflowLink('Documents',matter)} target="_blank" rel="noreferrer">Inspect source-work history</a></p><button disabled={busy} onClick={()=>{setPending(null);setSelected([]);setPeople([]);setAssignee('');setRefresh(v=>v+1);setMessage('Pending request dismissed after inspection. Refresh and select current revisions before making another change.');}}>I inspected the history; clear pending request</button></div>:<><button disabled={!selectionReady||busy} onClick={()=>void eligible()}>Find eligible assignees</button>{selected.length>25&&<p role="status">Reduce the selection to 25 tasks for reassignment. Exports allow up to 100.</p>}{selected.some(r=>!r.can_reassign)&&<p role="status">Some selected tasks cannot be reassigned by your account in their current state.</p>}{people.length>0&&<form className="task-reassignment-form" onSubmit={e=>{e.preventDefault();if(selectionReady&&assignee&&rationale.trim().length>=5)void submit({matter_id:matter,items:selected.map(r=>({id:r.id,expected_revision:r.revision})),assignee_id:assignee,rationale:rationale.trim(),request_key:crypto.randomUUID()});}}><label>New assignee<select required disabled={busy} value={assignee} onChange={e=>setAssignee(e.target.value)}><option value="">Choose an eligible person</option>{people.map(p=><option key={p.id} value={p.id}>{p.name} · {p.upn}</option>)}</select></label><label>Reason<textarea required minLength={5} maxLength={1000} disabled={busy} value={rationale} onChange={e=>setRationale(e.target.value)} placeholder="Explain the reassignment"/></label><button className="primary" disabled={busy||!selectionReady||!assignee||rationale.trim().length<5}>Reassign selected tasks</button></form>}</>}
  </details>
  {error&&<p className="error" role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
  <KestrelDataTable<TaskRow> dataset="tasks" matter={matter} csrf={csrf} columns={columns} filters={{task_filters:{historical,status:status||null,stage:stage||null,mine,...(created?{created_by:identity.id}:{})}}} refreshKey={refresh} onSelectedRows={setSelected} onDenied={deny} allowExport/>
  <small>Task completion records coordination work. Lawyer review, audience release and AI reruns retain their separate approval controls. Task saved views will follow with their own retained-evidence support.</small>
  {reader&&<DocumentReader target={reader} csrf={csrf} onClose={()=>setReader(null)}/>}
 </section>;
}
