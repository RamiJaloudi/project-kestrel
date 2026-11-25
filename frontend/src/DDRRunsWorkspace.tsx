import {useEffect,useRef,useState} from 'react';
import {workflowLink} from './WorkflowSteps';
import {selectPermittedMatter,useMatterSelection} from './matterSelection';

type Identity={id:string;organization:string;roles:string[]};
type Matter={id:string;name:string;client_number?:string;matter_number?:string};
type Finding={id:string;summary:string;source:string;playbook_id?:string};
type Options={findings:Finding[];playbooks:{id:string;name:string}[];agent_profiles:{id:string;name?:string;title?:string}[];live_enabled:boolean};
type ReviewTask={id:string;draft_hash:string;report_hash:string;snapshot_hash:string;config_hash:string;state:'pending'|'approved'|'rejected'|'revoked';report_id:string;can_decide:boolean;current_version?:boolean};
type Run={id:string;matter_id:string;title:string;audience:string;kind:string;engine:string;state:string;phase:string;created_at:number;error_code?:string|null;report_id?:string|null;requested_by?:string;can_cancel?:boolean;tasks?:ReviewTask[];events?:{kind:string;outcome:string;created_at:number}[]};
type Failure=Error&{status?:number};
const EMPTY:Options={findings:[],playbooks:[],agent_profiles:[],live_enabled:false};
const ROOT='/api/v1/ddr';
const hash=(value:string)=>/^[a-f0-9]{64}$/.test(value);
const taskKey=(task:ReviewTask)=>[task.id,task.draft_hash,task.report_hash,task.snapshot_hash,task.config_hash].join(':');
const readable=(value:string)=>value.replace(/_/g,' ');

export default function DDRRunsWorkspace({csrf,identity}:{csrf:string;identity:Identity}){
 const allowed=identity.organization==='firm'&&identity.roles.some(role=>['firm_lawyer','legal_sme','antitrust_counsel'].includes(role));
 const [matters,setMatters]=useState<Matter[]>([]),[matter,setMatter]=useMatterSelection();
 const [options,setOptions]=useState<Options>(EMPTY),[runs,setRuns]=useState<Run[]>([]),[selected,setSelected]=useState(''),[detail,setDetail]=useState<Run|null>(null);
 const [title,setTitle]=useState('Project Kestrel due diligence report'),[kind,setKind]=useState<'due_diligence'|'board_pack'>('due_diligence'),[audience,setAudience]=useState<'halden'|'castlegate'>('halden'),[engine,setEngine]=useState<'offline'|'openai'>('offline');
 const [checked,setChecked]=useState<string[]>([]),[playbook,setPlaybook]=useState(''),[profiles,setProfiles]=useState<string[]>([]),[rationale,setRationale]=useState('');
 const [reviewed,setReviewed]=useState<Record<string,boolean>>({}),[reasons,setReasons]=useState<Record<string,string>>({}),[cancelReason,setCancelReason]=useState('');
 const [busy,setBusy]=useState(false),[blocked,setBlocked]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[pending,setPending]=useState(false);
 const mounted=useRef(true),epoch=useRef(0),listTurn=useRef(0),detailTurn=useRef(0),controllers=useRef(new Set<AbortController>()),busyRef=useRef(false),blockedRef=useRef(false),selectedRef=useRef(''),taskStamp=useRef('');
 const requested=useRef(new URLSearchParams(location.search).get('run'));
 const submission=useRef<{signature:string;key:string}|null>(null);
 const scopeKey=[matter,csrf,identity.id,identity.organization,identity.roles.join(',')].join(':');
 const scope=useRef(scopeKey);scope.current=scopeKey;blockedRef.current=blocked;
 const userKey=[csrf,identity.id,identity.organization,identity.roles.join(',')].join(':');
 const user=useRef(userKey);user.current=userKey;

 function invalidate(){epoch.current++;listTurn.current++;detailTurn.current++;controllers.current.forEach(controller=>controller.abort());controllers.current.clear();}
 function resetProtected(){
  setOptions(EMPTY);setRuns([]);selectedRef.current='';setSelected('');setDetail(null);setChecked([]);setPlaybook('');setProfiles([]);setRationale('');setTitle('Project Kestrel due diligence report');setKind('due_diligence');setAudience('halden');setEngine('offline');setReviewed({});setReasons({});setCancelReason('');taskStamp.current='';submission.current=null;setPending(false);
 }
 function failure(value:unknown){
  const problem=value as Failure;if(problem.name==='AbortError'||!mounted.current)return;
  if(problem.status&&[401,403,409].includes(problem.status)){invalidate();resetProtected();requested.current=null;blockedRef.current=true;setBlocked(true);busyRef.current=false;setBusy(false);}
  setError(problem.message||'The DDR request could not be completed.');
 }
 async function api<T,>(path:string,body?:unknown):Promise<T>{
  const generation=epoch.current,key=scopeKey,controller=new AbortController();controllers.current.add(controller);
  try{
   const response=await fetch(path,{method:body===undefined?'GET':'POST',cache:'no-store',credentials:'same-origin',signal:controller.signal,headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});
   const value=await response.json().catch(()=>({detail:'DDR service is unavailable; refresh after it is restored.'}));
   if(!mounted.current||generation!==epoch.current||key!==scope.current)throw new DOMException('Discarded stale DDR response','AbortError');
   if(!response.ok)throw Object.assign(new Error(typeof value.detail==='string'?value.detail:'DDR request denied; check its fields and current permissions.'),{status:response.status});
   return value as T;
  }finally{controllers.current.delete(controller);}
 }
 function chooseRun(id:string){
  detailTurn.current++;selectedRef.current=id;setSelected(id);setDetail(null);setReviewed({});setReasons({});setCancelReason('');taskStamp.current='';
  const url=new URL(location.href);if(id)url.searchParams.set('run',id);else url.searchParams.delete('run');history.replaceState(null,'',url);
 }
 async function loadDetail(id:string){
  const turn=++detailTurn.current,value=await api<Run>(ROOT+'/runs/'+encodeURIComponent(id));
  if(turn!==detailTurn.current||selectedRef.current!==id)return;
  if(value.id!==id||value.matter_id!==matter)throw Object.assign(new Error('DDR run scope changed; reload the permitted workspace.'),{status:409});
  const stamp=JSON.stringify((value.tasks||[]).map(task=>[taskKey(task),task.state,task.current_version]));
  if(stamp!==taskStamp.current){taskStamp.current=stamp;setReviewed({});setReasons({});}
  setDetail(value);
 }
 async function refresh(){
  if(!allowed||!matter)return;
  const turn=++listTurn.current;
  const [list,available]=await Promise.all([api<Run[]>(ROOT+'/matters/'+encodeURIComponent(matter)+'/runs'),api<Options>(ROOT+'/matters/'+encodeURIComponent(matter)+'/evidence-options')]);
  if(turn!==listTurn.current)return;
  if(list.some(run=>run.matter_id!==matter))throw Object.assign(new Error('DDR response did not match the selected matter.'),{status:409});
  setRuns(list);setOptions(available);setError('');
  setChecked(previous=>previous.filter(id=>available.findings.some(finding=>finding.id===id)));
  setPlaybook(previous=>available.playbooks.some(book=>book.id===previous)?previous:'');
  setProfiles(previous=>previous.filter(id=>available.agent_profiles.some(profile=>profile.id===id)));
  if(!available.live_enabled)setEngine('offline');
  if(requested.current){const id=requested.current;requested.current=null;if(list.some(run=>run.id===id))chooseRun(id);else setError('The requested run is unavailable in this permitted matter.');}
  else if(selectedRef.current){if(list.some(run=>run.id===selectedRef.current))await loadDetail(selectedRef.current);else chooseRun('');}
 }
 async function act(work:()=>Promise<void>){
  if(busyRef.current)return;invalidate();busyRef.current=true;setBusy(true);setError('');setNotice('');const key=scopeKey;
  try{await work();}catch(value){failure(value);}finally{if(mounted.current&&key===scope.current){busyRef.current=false;setBusy(false);}}
 }

 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;invalidate();};},[]);
 useEffect(()=>{
  setMatters([]);if(!allowed)return;
  const controller=new AbortController(),key=userKey;
  fetch('/api/v1/workflow/matters',{cache:'no-store',credentials:'same-origin',signal:controller.signal}).then(async response=>{const value=await response.json();if(!response.ok)throw Object.assign(new Error(typeof value.detail==='string'?value.detail:'Permitted matters could not be loaded.'),{status:response.status});return value as Matter[];}).then(rows=>{if(mounted.current&&user.current===key){setMatters(rows);setMatter(selectPermittedMatter(rows));}}).catch(value=>{if(user.current===key)failure(value);});
  return()=>controller.abort();
 },[userKey,allowed]);
 useEffect(()=>{
  invalidate();resetProtected();blockedRef.current=false;setBlocked(false);busyRef.current=false;setBusy(false);setError('');setNotice('');
  if(!matter||!allowed)return;
  void refresh().catch(failure);
  const poll=()=>{if(!busyRef.current&&!blockedRef.current)void refresh().catch(failure);};
  const timer=setInterval(poll,15000),visible=()=>{if(document.visibilityState==='visible')poll();};
  const pageHide=()=>{invalidate();resetProtected();blockedRef.current=true;setBlocked(true);};
  document.addEventListener('visibilitychange',visible);window.addEventListener('pagehide',pageHide);
  return()=>{clearInterval(timer);document.removeEventListener('visibilitychange',visible);window.removeEventListener('pagehide',pageHide);invalidate();};
 },[scopeKey,allowed]);
 useEffect(()=>{if(selected&&selectedRef.current===selected&&!blockedRef.current)void loadDetail(selected).catch(failure);},[selected,scopeKey]);

 function changeMatter(value:string){requested.current=null;chooseRun('');setMatter(value);}
 async function create(){
  const body={matter_id:matter,finding_ids:checked,playbook_id:playbook,agent_profile_ids:profiles,title:title.trim(),audience,kind,engine,rationale:rationale.trim()};
  const signature=JSON.stringify(body);
  if(submission.current&&submission.current.signature!==signature)throw new Error('The earlier submission outcome is unresolved. Refresh runs or explicitly start a new request before changing its input.');
  if(!submission.current)submission.current={signature,key:crypto.randomUUID()};setPending(true);
  const value=await api<Run>(ROOT+'/matters/'+encodeURIComponent(matter)+'/runs',{...body,request_key:submission.current.key});
  submission.current=null;setPending(false);setRationale('');chooseRun(value.id);setDetail(value);await refresh();setNotice('Created an internal candidate run. Independent full-report review and separate audience release are still required.');
 }
 async function decide(task:ReviewTask,operation:'approve'|'reject'|'revoke'){
  const key=taskKey(task);
  await api<Run>(ROOT+'/tasks/'+encodeURIComponent(task.id)+'/decisions',{operation,draft_hash:task.draft_hash,report_hash:task.report_hash,snapshot_hash:task.snapshot_hash,config_hash:task.config_hash,content_reviewed:reviewed[key]===true,rationale:(reasons[key]||'').trim()});
  setReviewed({});setReasons({});await refresh();setNotice('Recorded '+operation+' for the exact internal report package. Audience publication remains a separate approval.');
 }
 const canCreate=!!matter&&!blocked&&!busy&&title.trim().length>=3&&rationale.trim().length>=10&&checked.length>=1&&checked.length<=30&&!!playbook&&profiles.length<=14&&(engine==='offline'||options.live_enabled);
 const cancellable=!!detail?.can_cancel&&!['cancelled','internally_approved','rejected','complete'].includes(detail?.state||'');

 if(!allowed)return <section><h2>Governed DDR runs</h2><p>Current assigned firm legal access is required. Root administration does not grant document or approval authority.</p></section>;
 return <section className="reports-workspace"><div className="section-heading"><h2>Governed DDR runs</h2><button disabled={busy||!matter} onClick={()=>{blockedRef.current=false;setBlocked(false);void act(refresh);}}>Refresh permitted scope</button></div>
  <p>Start from reviewed evidence, create an internal draft, then obtain an independent Legal SME review of the complete report and annexes. Nothing here automatically approves or releases content.</p>
  <label>Matter<select disabled={busy} value={matter} onChange={event=>changeMatter(event.target.value)}><option value="">Choose a permitted matter</option>{matters.map(item=><option key={item.id} value={item.id}>{item.client_number&&item.matter_number?item.client_number+'-'+item.matter_number+' · ':''}{item.name}</option>)}</select></label>
  {error&&<p className="error" role="alert">{error}</p>}{notice&&<p className="matter-saved" role="status">{notice}</p>}
  {blocked?<p role="status">Protected run data was cleared because the session, authorization scope or exact version changed. Refresh permitted scope before continuing.</p>:<>
   <details className="card matter-card" open={!runs.length}><summary>New DDR draft run</summary><p><b>Offline deterministic drafting is the default.</b> It uses the bounded reviewed-evidence workflow and does not call a model provider.</p>
    <div className="matter-form-grid"><label>Output<select disabled={busy} value={kind} onChange={event=>setKind(event.target.value as typeof kind)}><option value="due_diligence">Due diligence report</option><option value="board_pack">Board pack</option></select></label><label>Intended audience<select disabled={busy} value={audience} onChange={event=>setAudience(event.target.value as typeof audience)}><option value="halden">Halden</option><option value="castlegate">Castlegate</option></select></label><label>Draft engine<select disabled={busy} value={engine} onChange={event=>setEngine(event.target.value as typeof engine)}><option value="offline">Offline deterministic baseline</option><option value="openai" disabled={!options.live_enabled}>Controlled OpenAI {options.live_enabled?'available':'disabled pending approved activation'}</option></select></label><label>Published legal playbook<select disabled={busy} value={playbook} onChange={event=>setPlaybook(event.target.value)}><option value="">Choose an independently approved current version</option>{options.playbooks.map(book=><option key={book.id} value={book.id}>{book.name}</option>)}</select></label></div>
    {!options.live_enabled&&<p>Live provider execution is disabled. Selecting an intended audience does not grant that audience access.</p>}
    <label>Draft title<input disabled={busy} maxLength={160} minLength={3} value={title} onChange={event=>setTitle(event.target.value)}/></label>
    <fieldset disabled={busy}><legend>Reviewed findings · {checked.length} selected (maximum 30)</legend><div className="report-findings">{options.findings.map(finding=><label key={finding.id}><input type="checkbox" disabled={!checked.includes(finding.id)&&checked.length>=30} checked={checked.includes(finding.id)} onChange={event=>setChecked(previous=>event.target.checked?[...previous,finding.id]:previous.filter(id=>id!==finding.id))}/>{finding.summary}<small>{finding.source}</small></label>)}</div>{!options.findings.length&&<p>No currently permitted reviewed findings are available. Complete lawyer review first.</p>}</fieldset>
    <details><summary>Published specialist profiles (optional, maximum 14)</summary>{options.agent_profiles.length?<fieldset disabled={busy}>{options.agent_profiles.map(profile=><label key={profile.id}><input type="checkbox" disabled={!profiles.includes(profile.id)&&profiles.length>=14} checked={profiles.includes(profile.id)} onChange={event=>setProfiles(previous=>event.target.checked?[...previous,profile.id]:previous.filter(id=>id!==profile.id))}/>{profile.name||profile.title||profile.id}</label>)}</fieldset>:<p>No additional published profiles are configured. The bounded offline Contracts workflow remains available.</p>}</details>
    <label>Run rationale<textarea disabled={busy} minLength={10} maxLength={1000} value={rationale} onChange={event=>setRationale(event.target.value)}/></label>
    <button className="primary" disabled={!canCreate} onClick={()=>void act(create)}>{busy?'Submitting…':pending?'Retry exact submission':engine==='offline'?'Start offline DDR draft':'Start controlled live draft'}</button>
    {pending&&<p>The last submission has no confirmed response. Retry preserves its request key. <button disabled={busy} onClick={()=>{submission.current=null;setPending(false);setNotice('A new explicit request will use a new key. Inspect existing runs before submitting it.');}}>Start a new explicit request</button></p>}
   </details>
   <div className="report-layout"><section className="card matter-card"><h3>Permitted runs</h3>{runs.map(run=><button disabled={busy} className={'report-version '+(run.id===selected?'active':'')} key={run.id} onClick={()=>chooseRun(run.id)}><b>{run.title}</b><small>{run.engine==='offline'?'Offline deterministic':run.engine} · {readable(run.state)} · {readable(run.phase)}</small><small>{new Date(run.created_at*1000).toLocaleString()} · {run.audience}</small></button>)}{!runs.length&&<p>No permitted runs are available in this matter.</p>}</section>
    <section className="card matter-card">{!detail?<p>{selected?'Loading current permitted run…':'Select a permitted run to inspect its status and independent review tasks.'}</p>:<><h3>{detail.title}</h3><p>{readable(detail.state)} · {readable(detail.phase)} · {detail.engine==='offline'?'Offline deterministic candidate':detail.engine}</p>{detail.error_code&&<p className="error" role="status">Run stopped: {detail.error_code}. No provider request is automatically retried here.</p>}{detail.report_id&&<p><a href={workflowLink('Reports & Board Pack',matter)+'&report='+encodeURIComponent(detail.report_id)}>Open current saved report and annexes</a></p>}
     {cancellable&&<details><summary>Cancel future run work</summary><label>Cancellation rationale<textarea disabled={busy} minLength={10} maxLength={1000} value={cancelReason} onChange={event=>setCancelReason(event.target.value)}/></label><button disabled={busy||cancelReason.trim().length<10} onClick={()=>void act(async()=>{await api(ROOT+'/runs/'+encodeURIComponent(detail.id)+'/cancel',{rationale:cancelReason.trim()});setCancelReason('');await refresh();setNotice('Cancelled future run work. Retained evidence, attempts and decisions remain.');})}>Cancel run</button></details>}
     <h4>Independent full-report review</h4>{!detail.tasks?.length&&<p>No human review task is ready. A graph status update never counts as an approval.</p>}
     {detail.tasks?.map(task=>{const key=taskKey(task),reason=reasons[key]||'',exact=[task.draft_hash,task.report_hash,task.snapshot_hash,task.config_hash].every(hash),canReview=task.can_decide&&task.current_version!==false&&task.state==='pending';return <article className="report-approval" key={key}><h4>Saved report task · {task.state}</h4><div className="api-links"><a href={workflowLink('Reports & Board Pack',matter)+'&report='+encodeURIComponent(task.report_id)}>Read complete saved report, citations and annexes</a><a href={'/api/v1/reports/'+encodeURIComponent(task.report_id)+'/download/docx'}>Download exact Word report</a></div>
      {task.current_version===false&&<p>A newer saved report version has its own task. Earlier decisions remain retained.</p>}
      <details><summary>Exact version hashes</summary><dl style={{overflowWrap:'anywhere'}}>{(['report_hash','draft_hash','snapshot_hash','config_hash'] as const).map(field=><div key={field}><dt>{readable(field)}</dt><dd><code>{task[field]}</code></dd></div>)}</dl></details>
      {canReview&&<label><input type="checkbox" disabled={busy} checked={reviewed[key]===true} onChange={event=>setReviewed(previous=>({...previous,[key]:event.target.checked}))}/>I reviewed this complete saved report, original citations and both annexes, including the Word document. I am recording an independent internal review of this exact version.</label>}
      {task.can_decide&&task.current_version!==false&&['pending','approved'].includes(task.state)&&<><label>Review or revocation rationale<textarea disabled={busy} minLength={10} maxLength={1000} value={reason} onChange={event=>setReasons(previous=>({...previous,[key]:event.target.value}))}/></label><div className="api-links">{canReview&&<><button disabled={busy||!exact||!reviewed[key]||reason.trim().length<10} onClick={()=>void act(()=>decide(task,'approve'))}>Approve exact internal report</button><button disabled={busy||!exact||!reviewed[key]||reason.trim().length<10} onClick={()=>void act(()=>decide(task,'reject'))}>Reject exact internal report</button></>}{task.state==='approved'&&<button disabled={busy||!exact||reason.trim().length<10} onClick={()=>void act(()=>decide(task,'revoke'))}>Revoke internal approval</button>}</div></>}
      {!task.can_decide&&<p>A different currently cleared Legal SME must review the current saved version.</p>}<small>Internal review does not publish to Halden or Castlegate. Audience release and any antitrust approval remain separate.</small>
     </article>;})}
     {!!detail.events?.length&&<details><summary>Retained run events</summary><ul>{detail.events.map((event,index)=><li key={index}>{new Date(event.created_at*1000).toLocaleString()} · {readable(event.kind)} · {readable(event.outcome)}</li>)}</ul></details>}
    </>}</section>
   </div><small>Current permissions and run status refresh every 15 seconds. Report text is opened through its existing protected reader.</small>
  </>}
 </section>;
}
