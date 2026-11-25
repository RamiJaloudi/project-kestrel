import {useEffect,useRef,useState,type FormEvent} from 'react';
import KestrelDataTable,{type AuditTableQuery,type TableColumn} from './KestrelDataTable';

type AuditFilters=AuditTableQuery['audit_filters'];
type Category=AuditFilters['category'];
type Format='jsonl'|'csv'|'html'|'pdf';
type AuditRow={id:string;occurred_at:number;actor_id:string|null;category:string;matter_id:string|null;object_id:string|null;clean_team_scope:string|null;action:string;outcome:string;correlation_id:string|null};
type Failure=Error&{status?:number};
const categories:Category[]=['administrative','legal_sme','clean_team','access'];
const formats:Format[]=['jsonl','csv','html','pdf'];
const label=(value:string)=>value.replace(/_/g,' ');
function localMinute(value:number){const date=new Date(value),pad=(part:number)=>String(part).padStart(2,'0');return date.getFullYear()+'-'+pad(date.getMonth()+1)+'-'+pad(date.getDate())+'T'+pad(date.getHours())+':'+pad(date.getMinutes());}
function utc(value:number){const date=new Date(value*1000);return Number.isFinite(date.getTime())?date.toISOString().replace('T',' ').replace('.000Z',' UTC'):'Unavailable';}
function epochTime(value:string,name:string){
 if(!value)return undefined;const seconds=Math.floor(new Date(value).getTime()/1000);
 if(!Number.isFinite(seconds)||!Number.isSafeInteger(seconds)||seconds<0)throw new Error(name+' must be a valid time on or after the Unix epoch.');return seconds;
}

export default function AuditWorkspace({csrf,accountId,preview=false}:{csrf:string;accountId?:string;preview?:boolean}){
 if(preview||!accountId||!csrf)return <section className="card hub-details"><h2>Scoped audit reports</h2><p>{preview?'Read-only preview: sign in to query or export audit records.':'Sign in to query your permitted audit activity.'}</p><p>Audit access does not override ethical walls or named clean-team restrictions.</p></section>;
 return <ScopedAudit key={accountId+':'+csrf} csrf={csrf}/>;
}

function ScopedAudit({csrf}:{csrf:string}){
 const [initialWindow]=useState(()=>{const end=Math.floor(Date.now()/60000)*60000;return {from:localMinute(end-3600000),to:localMinute(end)};});
 const [category,setCategory]=useState<Category>('administrative'),[matter,setMatter]=useState(()=>new URLSearchParams(location.search).get('matter')||''),[from,setFrom]=useState(initialWindow.from),[to,setTo]=useState(initialWindow.to);
 const [applied,setApplied]=useState<AuditFilters|null>(null),[loadedQuery,setLoadedQuery]=useState<AuditTableQuery|null>(null),[application,setApplication]=useState(0),[exporting,setExporting]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const alive=useRef(true),epoch=useRef(0),exportPending=useRef<AbortController|null>(null),exportBusy=useRef(false),queryRef=useRef<AuditTableQuery|null>(null),scopeSerial=useRef(0),appliedRef=useRef<AuditFilters|null>(null),urls=useRef(new Set<string>());
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;epoch.current++;exportPending.current?.abort();for(const url of urls.current)URL.revokeObjectURL(url);urls.current.clear();};},[]);
 function invalidate(){
  epoch.current++;exportPending.current?.abort();exportPending.current=null;exportBusy.current=false;queryRef.current=null;setLoadedQuery(null);setExporting(false);setNotice('');
 }
 function editScope(){scopeSerial.current++;appliedRef.current=null;invalidate();setApplied(null);setError('');}
 function apply(event:FormEvent){
  event.preventDefault();scopeSerial.current++;appliedRef.current=null;invalidate();setApplied(null);setError('');
  try{
   const fromTime=epochTime(from,'From time'),toTime=epochTime(to,'To time'),selectedMatter=matter.trim();
   if(selectedMatter.length>36||/[\x00-\x1f\x7f]/.test(selectedMatter))throw new Error('Enter a valid matter ID of at most 36 characters.');
   if(fromTime!==undefined&&toTime!==undefined&&fromTime>toTime)throw new Error('From time must precede or equal To time.');
   const next:AuditFilters={category,...(selectedMatter?{matter_id:selectedMatter}:{}),...(fromTime===undefined?{}:{from_time:fromTime}),...(toTime===undefined?{}:{to_time:toTime})};appliedRef.current=next;setApplied(next);setApplication(scopeSerial.current);
  }catch(value){setError((value as Error).message);}
 }
 function queryLoaded(query:AuditTableQuery|null,scope:number){
  if(!alive.current||scope!==scopeSerial.current||!appliedRef.current)return;
  if(!query){invalidate();return;}
  if(JSON.stringify(query.audit_filters)!==JSON.stringify(appliedRef.current)){deny('The loaded audit scope did not match the applied filters. Apply the scope again.');return;}
  const snapshot:AuditTableQuery={...query,audit_filters:{...query.audit_filters},column_filters:{...(query.column_filters||{})}};
  queryRef.current=snapshot;setLoadedQuery(snapshot);
 }
 function deny(message='The current session or audit permissions changed. Apply a currently permitted audit scope before continuing.'){
  scopeSerial.current++;appliedRef.current=null;invalidate();setApplied(null);setError(message);
 }
 async function download(format:Format){
  const query=queryRef.current;if(!query||!appliedRef.current||exportBusy.current)return;
  const turn=epoch.current,controller=new AbortController();exportPending.current=controller;exportBusy.current=true;setExporting(true);setError('');setNotice('');
  try{
   const response=await fetch('/api/v1/audit/export-query',{method:'POST',cache:'no-store',signal:controller.signal,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({...query,format})});
   if(!response.ok){const value=await response.json().catch(()=>null);throw Object.assign(new Error(typeof value?.detail==='string'?value.detail:'Audit export unavailable. Refresh your scope and try again.'),{status:response.status});}
   if((response.headers.get('Content-Type')||'').split(';')[0].trim().toLowerCase()!=='application/zip')throw new Error('The server did not return an audit ZIP package.');
   const blob=await response.blob();if(!alive.current||controller.signal.aborted||turn!==epoch.current)return;
   const url=URL.createObjectURL(blob),link=document.createElement('a');urls.current.add(url);link.href=url;link.download='kestrel-audit-'+format+'.zip';link.click();
   setTimeout(()=>{URL.revokeObjectURL(url);urls.current.delete(url);},10000);setNotice('Audit ZIP downloaded. Its manifest records the applied scope, searches and exact event IDs.');
  }catch(value){
   if(alive.current&&!controller.signal.aborted&&turn===epoch.current){const failure=value as Failure;if([401,403,409].includes(failure.status||0))deny(failure.message);else{invalidate();setError(failure.message);}}
  }finally{if(alive.current&&exportPending.current===controller){exportPending.current=null;exportBusy.current=false;setExporting(false);}}
 }
 const columns:TableColumn<AuditRow>[]=[
  {key:'occurred_at',title:'Time (UTC)',render:row=>utc(row.occurred_at)},
  {key:'action',title:'Action'},
  {key:'outcome',title:'Outcome'},
  {key:'object_id',title:'Object ID',render:row=><span className="audit-reference">{row.object_id??'—'}</span>},
  {key:'category',title:'Category',render:row=>label(row.category)},
  {key:'matter_id',title:'Matter ID',render:row=><span className="audit-reference">{row.matter_id??'—'}</span>},
  {key:'actor_id',title:'Actor ID',visible:false,render:row=><span className="audit-reference">{row.actor_id??'—'}</span>},
  {key:'clean_team_scope',title:'Clean-team scope',visible:false,render:row=><span className="audit-reference">{row.clean_team_scope??'—'}</span>},
  {key:'correlation_id',title:'Correlation ID',visible:false,render:row=><span className="audit-reference">{row.correlation_id??'—'}</span>},
  {key:'id',title:'Event ID',visible:false,render:row=><span className="audit-reference">{row.id}</span>}
 ];
 return <section className="card hub-details"><h2>Scoped audit reports</h2><p>Own permitted activity or explicitly authorized matter timelines. Clean-team access requires active named scope; Root Admin has no override. No automatic deletion.</p>
  <form onSubmit={apply} aria-label="Audit scope"><div className="matter-form-grid"><label>Category<select value={category} onChange={event=>{editScope();setCategory(event.target.value as Category);}}>{categories.map(value=><option key={value} value={value}>{label(value)}</option>)}</select></label><label>Matter ID (optional)<input maxLength={36} value={matter} onChange={event=>{editScope();setMatter(event.target.value);}}/></label><label>From (local time)<input type="datetime-local" value={from} onChange={event=>{editScope();setFrom(event.target.value);}}/></label><label>To (local time)<input type="datetime-local" value={to} onChange={event=>{editScope();setTo(event.target.value);}}/></label></div><button className="primary" type="submit">Apply audit scope</button></form>
  <p className="matter-subtle">The permitted category/matter/time window is limited to 1,000 events before search. Narrow the matter or time window if it exceeds this limit; results are never silently truncated.</p>
  {error&&<p className="error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  {applied?<><p role="status">Applied: {label(applied.category)} · {applied.matter_id||'all permitted scopes'} · {applied.from_time===undefined?'no lower time bound':utc(applied.from_time)} → {applied.to_time===undefined?'no upper time bound':utc(applied.to_time)}</p><KestrelDataTable<AuditRow> key={application} dataset="audit" csrf={csrf} columns={columns} filters={{audit_filters:applied}} selectable={false} onAuditQuery={query=>queryLoaded(query,application)} pauseRefresh={exporting} onDenied={()=>{if(application===scopeSerial.current)deny();}}/></>:<p role="status">Choose a scope and apply it to load permitted audit events.</p>}
  <div className="api-links" aria-label="Audit package exports">{formats.map(format=><button key={format} type="button" disabled={!loadedQuery||exporting} onClick={()=>void download(format)}>Export {format.toUpperCase()} + manifest</button>)}</div>
  <p>{loadedQuery?'Exports include all searched events in the applied window, across every page.':'Export becomes available after the current table query loads successfully.'} ZIP integrity manifests are not immutable/WORM storage. Immutable-storage integration remains unconfigured.</p>
 </section>;
}
