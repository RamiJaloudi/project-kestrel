import {createContext,useContext,useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import DataTable,{Column} from 'datatables.net-react';
import DtCore from 'datatables.net-dt';
import type {Options,Api} from 'datatables.net';
import SavedTableViews,{type SavedTableConfiguration,type SavedTableQuery} from './SavedTableViews';
import 'datatables.net-dt/css';
export type {SavedTableQuery} from './SavedTableViews';
DataTable.use(DtCore);

export type TableDataset='inventory'|'financial'|'tasks'|'findings'|'accounts'|'audit'|'registry_access'|'registry_history';
export type TableColumn<T>={key:Extract<keyof T,string>;title:string;orderable?:boolean;searchable?:boolean;visible?:boolean;render?:(row:T)=>ReactNode};
type FixedSourceFilters={historical?:boolean;contracts_only?:boolean};
type DirectoryFilters={account_filters?:{organization?:'firm'|'halden'|'castlegate';active?:boolean}};
type AuditFilters={category:'administrative'|'legal_sme'|'clean_team'|'access';matter_id?:string;from_time?:number;to_time?:number};
export type AuditTableQuery=Pick<SavedTableQuery,'draw'|'start'|'length'|'sort'|'direction'|'search'|'column_filters'>&{audit_filters:AuditFilters};
type CommonProps<T extends {id:string}>={csrf:string;columns:TableColumn<T>[];initialOrder?:{column:Extract<keyof T,string>;direction:'asc'|'desc'};refreshKey?:number;pauseRefresh?:boolean;onDenied?:()=>void};
type UnselectedProps={matter?:never;fixedSourceFilters?:never;selectable?:false;allowExport?:false;onSelection?:never;onSelectedRows?:never;onEffectiveQuery?:never};
type Props<T extends {id:string}>=CommonProps<T>&(
 (UnselectedProps&{dataset:'accounts';filters?:DirectoryFilters;onAuditQuery?:never;onStale?:never})
 |(UnselectedProps&{dataset:'audit';filters:{audit_filters:AuditFilters};onAuditQuery?:(query:AuditTableQuery|null)=>void;onStale?:never})
 |(Omit<UnselectedProps,'matter'>&{dataset:'registry_access'|'registry_history';matter:string;filters?:never;onAuditQuery?:never;onStale?:(message:string)=>void})
 |{dataset:Exclude<TableDataset,'accounts'|'audit'|'registry_access'|'registry_history'>;matter:string;filters?:Record<string,unknown>;fixedSourceFilters?:FixedSourceFilters;selectable?:boolean;allowExport?:boolean;onSelection?:(ids:string[])=>void;onSelectedRows?:(rows:T[])=>void;onEffectiveQuery?:(query:SavedTableQuery|null)=>void;onAuditQuery?:never;onStale?:never}
);
type DirectoryQuery=Pick<SavedTableQuery,'draw'|'start'|'length'|'sort'|'direction'|'search'|'column_filters'>&DirectoryFilters;
type ActiveQuery=SavedTableQuery|DirectoryQuery|AuditTableQuery;
const queryEndpoints:Record<TableDataset,string>={inventory:'/api/v1/tables/inventory/query',financial:'/api/v1/tables/financial/query',tasks:'/api/v1/tables/tasks/query',findings:'/api/v1/tables/findings/query',accounts:'/api/v1/admin/accounts/query',audit:'/api/v1/audit/query',registry_access:'/api/v1/validation/tables/access/query',registry_history:'/api/v1/validation/tables/history/query'};
const isMatterQuery=(query:ActiveQuery):query is SavedTableQuery=>'matter_id' in query;
const isAuditQuery=(query:ActiveQuery):query is AuditTableQuery=>'audit_filters' in query;
type GridRequest={draw?:number;start?:number;length?:number;search?:{value?:string};order?:{column:number;dir:'asc'|'desc'}[];columns?:{name:string;search?:{value?:string}}[]};
type TableHandle={dt:()=>Api|null};
type Failure=Error&{status?:number};
type RenderContext={render:(key:string,row:unknown)=>ReactNode;selected:Set<string>;toggle:(row:unknown)=>void};
const Cells=createContext<RenderContext>({render:()=>null,selected:new Set(),toggle:()=>{}});
function Cell({field,row}:{field:string;row:unknown}){return <>{useContext(Cells).render(field,row)}</>;}
function SelectCell({row,label}:{row:{id:string};label:string}){const context=useContext(Cells);return <input aria-label={'Select '+label} type="checkbox" checked={context.selected.has(row.id)} onChange={()=>context.toggle(row)}/>;}
const filterSummary=(filters:Record<string,unknown>)=>Object.values(filters).flatMap(value=>Object.entries((value||{}) as Record<string,unknown>).filter(([,v])=>v!==null&&v!==false&&v!=='').map(([key,v])=>key.replace(/_/g,' ')+': '+(v===true?'yes':String(v).replace(/_/g,' ')))).join(' · ')||'No additional typed filters';
function constrainedFilters(filters:Record<string,unknown>,fixed?:FixedSourceFilters):Record<string,unknown>{
 return fixed?{...filters,source_filters:{...(filters.source_filters as Record<string,unknown>|undefined),...fixed}}:filters;
}

async function jsonResponse<T,>(response:Response):Promise<T>{
 const value=await response.json().catch(()=>null);
 if(!response.ok)throw Object.assign(new Error(typeof value?.detail==='string'?value.detail:'Table request unavailable. Refresh and check your filters and current permissions.'),{status:response.status});
 if(value===null)throw new Error('The table returned an unreadable response. Refresh before continuing.');
 return value as T;
}

export default function KestrelDataTable<T extends {id:string}>(props:Props<T>){
 // New authenticated scopes own fresh grids and no pending selections/exports.
 return <ScopedDataTable<T> key={props.dataset+':'+(props.matter||'directory')+':'+props.csrf+':'+JSON.stringify(props.fixedSourceFilters||{})+':'+String(props.selectable!==false)+':'+JSON.stringify(props.initialOrder||{})} {...props}/>;
}

function ScopedDataTable<T extends {id:string}>({dataset,matter,csrf,columns,initialOrder,filters={},fixedSourceFilters,selectable:selectionEnabled,refreshKey=0,pauseRefresh=false,onDenied,onSelection,onSelectedRows,onEffectiveQuery,onAuditQuery,onStale,allowExport=false}:Props<T>){
 const selectable=dataset!=='accounts'&&dataset!=='audit'&&dataset!=='registry_access'&&dataset!=='registry_history'&&selectionEnabled!==false;
 const ref=useRef<TableHandle>(null),element=useRef<HTMLElement|null>(null),pending=useRef<AbortController|null>(null),exportPending=useRef<AbortController|null>(null),alive=useRef(true),epoch=useRef(0);
 const [error,setError]=useState(''),[notice,setNotice]=useState(''),[selection,setSelection]=useState<Map<string,T>>(new Map()),[exporting,setExporting]=useState(false),[blocked,setBlocked]=useState(false);
 const [visible,setVisible]=useState<Record<string,boolean>>(()=>Object.fromEntries(columns.map(column=>[column.key,column.visible!==false]))),[columnSearch,setColumnSearch]=useState<Record<string,string>>({});
 const [saved,setSaved]=useState<SavedTableConfiguration|null>(null),[loadedFilters,setLoadedFilters]=useState<Record<string,unknown>|null>(null);
 const queryRef=useRef<ActiveQuery>({...matter?{matter_id:matter}:{},draw:0,start:0,length:20,direction:'asc',search:'',column_filters:{},...constrainedFilters(filters,fixedSourceFilters)});
 const latest=useRef({dataset,matter,csrf,filters,fixedSourceFilters,columns,pauseRefresh,onDenied,onSelection,onSelectedRows,onEffectiveQuery,onAuditQuery,onStale,saved,loadedFilters});
 latest.current={dataset,matter,csrf,filters,fixedSourceFilters,columns,pauseRefresh,onDenied,onSelection,onSelectedRows,onEffectiveQuery,onAuditQuery,onStale,saved,loadedFilters};
 const selected=useMemo(()=>new Set(selection.keys()),[selection]),selectionQuery=useRef('');
 const visibleWindow=useRef<{key:string;ids:Set<string>}>({key:'',ids:new Set()});
 function clearSelection(){setSelection(previous=>previous.size?new Map():previous);}
 function invalidateSelection(){epoch.current++;exportPending.current?.abort();setExporting(false);clearSelection();}
 function deny(){
  pending.current?.abort();invalidateSelection();setBlocked(true);setSaved(null);setLoadedFilters(null);setNotice('');
  latest.current.saved=null;latest.current.loadedFilters=null;latest.current.onEffectiveQuery?.(null);latest.current.onAuditQuery?.(null);latest.current.onDenied?.();
 }
 const context=useMemo<RenderContext>(()=>({selected,toggle:raw=>setSelection(previous=>{
  const row=raw as T,next=new Map(previous);if(next.has(row.id))next.delete(row.id);else if(next.size<100)next.set(row.id,row);return next;
 }),render:(key,row)=>{const column=columns.find(c=>c.key===key);return column?.render?column.render(row as T):String((row as Record<string,unknown>)[key]??'');}}),[selected,columns]);

 const ajax=useMemo<Extract<NonNullable<Options['ajax']>,Function>>(()=>((raw,callback)=>{
  const request=raw as unknown as GridRequest,scope=latest.current;
  scope.onAuditQuery?.(null);
  pending.current?.abort();const controller=new AbortController();pending.current=controller;
  const ordered=request.order?.[0],name=ordered?request.columns?.[ordered.column]?.name:undefined;
  const column=scope.columns.find(c=>c.key===name&&c.orderable!==false);
  const columnFilters=Object.fromEntries((request.columns||[]).filter(c=>c.name!=='_select'&&!!c.search?.value).map(c=>[c.name,c.search?.value]));
  const typed=constrainedFilters(scope.loadedFilters||scope.filters,scope.fixedSourceFilters);
  const query:ActiveQuery={...scope.matter?{matter_id:scope.matter}:{},draw:request.draw||0,start:request.start||0,length:request.length||20,sort:column?.key||scope.columns.find(c=>c.orderable!==false)?.key,direction:ordered?.dir||'asc',search:request.search?.value||'',column_filters:columnFilters as Record<string,string>,...typed};
  if(scope.saved&&isMatterQuery(query)){
   const stored=scope.saved.query,entries=(value:Record<string,string>)=>JSON.stringify(Object.entries(value).filter(([,v])=>!!v).sort());
   const unchanged=query.search===(stored.search||'')&&query.length===(stored.length||20)&&query.sort===(stored.sort||scope.columns.find(c=>c.orderable!==false)?.key)&&query.direction===(stored.direction||'asc')&&entries(query.column_filters||{})===entries(stored.column_filters||{});
   if(unchanged){query.saved_view_id=scope.saved.id;query.saved_view_version_hash=scope.saved.version_hash;}
   else{latest.current.saved=null;setSaved(null);scope.onEffectiveQuery?.(query);setNotice('Live query edited. The saved configuration is unchanged.');}
  }
  const signature=JSON.stringify({search:query.search,columns:query.column_filters,filters:typed});
  const windowKey=JSON.stringify({signature,start:query.start,length:query.length,sort:query.sort,direction:query.direction});
  if(selectionQuery.current!==signature){selectionQuery.current=signature;invalidateSelection();}
  queryRef.current=query;
  fetch(queryEndpoints[scope.dataset],{method:'POST',cache:'no-store',signal:controller.signal,headers:{'Content-Type':'application/json','X-CSRF-Token':scope.csrf},body:JSON.stringify(query)})
   .then(jsonResponse<{data:T[]}>).then(value=>{if(alive.current&&!controller.signal.aborted){
    setError('');const current=new Map(value.data.map(row=>[row.id,row])),priorWindow=visibleWindow.current;
    setSelection(previous=>{const next=new Map(previous);for(const [id,row] of previous){const updated=current.get(id);if(updated?JSON.stringify(updated)!==JSON.stringify(row):priorWindow.key===windowKey&&priorWindow.ids.has(id))next.delete(id);}return next.size===previous.size?previous:next;});
    visibleWindow.current={key:windowKey,ids:new Set(current.keys())};callback(value);
    if(scope.dataset==='audit'&&isAuditQuery(query)){
     // A timer draw may finish while a newly typed search is still debouncing.
     const currentSearch=element.current?.querySelector<HTMLInputElement>('.dt-search input')?.value||'';
     scope.onAuditQuery?.(query.search===currentSearch?query:null);
    }
   }})
   .catch((failure:Failure)=>{if(alive.current&&!controller.signal.aborted){setError(failure.message);scope.onAuditQuery?.(null);if(failure.status===409&&scope.onStale&&(scope.dataset==='registry_access'||scope.dataset==='registry_history')){invalidateSelection();scope.onStale(failure.message);}else if([401,403,409].includes(failure.status||0))deny();callback({draw:request.draw||0,recordsTotal:0,recordsFiltered:0,data:[]});}}).finally(()=>{if(pending.current===controller)pending.current=null;});
 }),[]);
 const options=useMemo<Options>(()=>{const requestedOrder=columns.findIndex(c=>c.key===initialOrder?.column&&c.orderable!==false),orderIndex=requestedOrder>=0?requestedOrder:Math.max(0,columns.findIndex(c=>c.orderable!==false));return {serverSide:true,processing:true,pageLength:20,lengthMenu:[10,20,50],searchDelay:400,order:[[orderIndex+(selectable?1:0),initialOrder?.direction||'asc']],autoWidth:false,language:{emptyTable:'No permitted records match this scope.',processing:'Checking authorized records…'},layout:{topStart:'pageLength',topEnd:'search',bottomStart:'info',bottomEnd:'paging'}};},[]);
 useEffect(()=>{if(selectable){latest.current.onSelection?.([...selection.keys()]);latest.current.onSelectedRows?.([...selection.values()]);}},[selection]);
 const fingerprint=JSON.stringify(filters),first=useRef(true),lastFingerprint=useRef(fingerprint);
 useEffect(()=>{
  if(first.current){first.current=false;return;}
  invalidateSelection();
  if(lastFingerprint.current!==fingerprint){lastFingerprint.current=fingerprint;setSaved(null);setLoadedFilters(null);latest.current.saved=null;latest.current.loadedFilters=null;latest.current.onEffectiveQuery?.(null);}
  ref.current?.dt()?.ajax.reload(undefined,true);
 },[fingerprint,refreshKey]);
 useEffect(()=>{
  alive.current=true;const timer=setInterval(()=>{if(!pending.current&&!latest.current.pauseRefresh)ref.current?.dt()?.ajax.reload(undefined,false);},15000);
  return()=>{alive.current=false;epoch.current++;pending.current?.abort();exportPending.current?.abort();clearInterval(timer);};
 },[]);

 function applySearch(clear=false){
  const api=ref.current?.dt();if(!api)return;
  // Column filters can be applied before the global search debounce finishes.
  // Carry that visible draft into the same draw rather than clearing it.
  api.search(clear?'':element.current?.querySelector<HTMLInputElement>('.dt-search input')?.value||'');
  for(const column of columns)if(column.searchable!==false)api.column(column.key+':name').search(clear?'':columnSearch[column.key]||'');
  if(clear){api.search('');setColumnSearch({});}api.draw();
 }
 function applyConfiguration(value:SavedTableConfiguration|null){
  const query=value?.query;
  if(value&&(value.matter_id!==matter||value.dataset!==dataset))throw new Error('Saved query does not match this table and matter.');
  if(query?.sort&&!columns.some(c=>c.key===query.sort&&c.orderable!==false))throw new Error('Choose a saved query sorted by one of this table’s sortable columns.');
  if(query&&Object.keys(query.column_filters||{}).some(key=>!columns.some(c=>c.key===key)))throw new Error('Choose a saved query using this table’s columns.');
  if(query&&fixedSourceFilters&&Object.entries(fixedSourceFilters).some(([key,required])=>required!==undefined&&(query.source_filters?.[key]===undefined?false:query.source_filters[key])!==required))throw new Error('Choose a current contract-only saved query for this register.');
  const typed=query?{...(query.source_filters?{source_filters:query.source_filters}:{}),...(query.financial_filters?{financial_filters:query.financial_filters}:{})}:null;
  pending.current?.abort();invalidateSelection();setSaved(value);setLoadedFilters(typed);latest.current.saved=value;latest.current.loadedFilters=typed;
  setColumnSearch(query?.column_filters||{});latest.current.onEffectiveQuery?.(query||null);
  const api=ref.current?.dt();if(!api)return;
  for(const column of columns)api.column(column.key+':name').search(query?.column_filters?.[column.key]||'');
  api.search(query?.search||'');api.page.len(query?.length||20);
  const index=columns.findIndex(c=>c.key===(query?.sort||columns.find(c=>c.orderable!==false)?.key));
  if(index>=0)api.order([[index+(selectable?1:0),query?.direction||'asc']]);api.draw();
 }
 function savedQuery(){const query=queryRef.current;if(!isMatterQuery(query))throw new Error('Directory queries cannot be saved.');return {...query};}
 async function download(format:'csv'|'xlsx'){
  if(!selectable||!allowExport)return;
  const generation=epoch.current,scope=latest.current,controller=new AbortController();
  exportPending.current?.abort();exportPending.current=controller;setExporting(true);setError('');setNotice('');
  try{
   const typed=constrainedFilters(scope.loadedFilters||scope.filters,scope.fixedSourceFilters);
   const historical=!!((typed.source_filters||typed.task_filters||typed.finding_filters) as {historical?:boolean}|undefined)?.historical;
   const revisions=scope.dataset==='findings'?{finding_versions:Object.fromEntries([...selection.values()].map(row=>[row.id,(row as T&{revision_id:string}).revision_id]))}:{};
   const response=await fetch('/api/v1/tables/'+scope.dataset+'/export',{method:'POST',cache:'no-store',signal:controller.signal,headers:{'Content-Type':'application/json','X-CSRF-Token':scope.csrf},body:JSON.stringify({matter_id:scope.matter,ids:[...selection.keys()],format,historical,...revisions})});
   if(!response.ok)await jsonResponse(response);
   const media=response.headers.get('Content-Type')||'';
   if(!media.includes(format==='csv'?'text/csv':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))throw new Error('The server did not return the requested export format.');
   const blob=await response.blob();if(!alive.current||controller.signal.aborted||generation!==epoch.current)return;
   const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='kestrel-'+scope.dataset+'-internal.'+format;link.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
   const unavailable=Number(response.headers.get('X-Export-Unavailable-Count')||'0');
   setNotice('Export ready: '+Math.max(0,selection.size-unavailable)+' rows included; '+unavailable+' unavailable under current retained handling. Internal metadata only; external release is separate.');
  }catch(value){if(alive.current&&!controller.signal.aborted&&generation===epoch.current){const failure=value as Failure;setError(failure.message);if([401,403,409].includes(failure.status||0))deny();}}
  finally{if(alive.current&&generation===epoch.current)setExporting(false);}
 }

 return <section ref={element} className="kestrel-data-table" aria-label={dataset+' records'} onInputCapture={event=>{if(dataset==='audit'&&(event.target as HTMLElement).matches('.dt-search input'))latest.current.onAuditQuery?.(null);}}>
  {!blocked&&(dataset==='inventory'||dataset==='financial')&&<SavedTableViews key={matter+':'+dataset} matter={matter!} dataset={dataset} csrf={csrf} internal={allowExport} selected={[...selection.keys()]} getQuery={savedQuery} onLoad={applyConfiguration} onClear={()=>applyConfiguration(null)} onDenied={deny}/>}
  {loadedFilters&&<p role="status">{saved?'Saved query: '+saved.name:'Loaded typed filters'} · {filterSummary(loadedFilters)} <button onClick={()=>applyConfiguration(null)}>Use workspace filters</button></p>}
  <div className="table-tools">
   <details><summary>Columns</summary>{columns.map(column=><label key={column.key}><input type="checkbox" checked={visible[column.key]!==false} onChange={event=>{setVisible({...visible,[column.key]:event.target.checked});ref.current?.dt()?.column(column.key+':name').visible(event.target.checked);}}/>{column.title}</label>)}</details>
   <details><summary>Column filters</summary><div className="source-work-columns">{columns.filter(column=>column.searchable!==false).map(column=><label key={column.key}>{column.title}<input value={columnSearch[column.key]||''} maxLength={128} onChange={event=>setColumnSearch({...columnSearch,[column.key]:event.target.value})}/></label>)}</div><button onClick={()=>applySearch()}>Apply column filters</button><button onClick={()=>applySearch(true)}>Clear table searches</button></details>
   {selectable&&<><span>{selection.size} selected (maximum 100)</span><button disabled={blocked} onClick={()=>{const rows=ref.current?.dt()?.rows({page:'current'}).data().toArray() as T[]|undefined;if(rows)setSelection(previous=>{const next=new Map(previous);for(const row of rows)if(next.size<100&&!next.has(row.id))next.set(row.id,row);return next;});}}>Select this page</button><button onClick={clearSelection} disabled={!selection.size}>Clear selection</button>
   {allowExport&&<><button disabled={!selection.size||exporting||blocked} onClick={()=>void download('csv')}>Export selected CSV</button><button disabled={!selection.size||exporting||blocked} onClick={()=>void download('xlsx')}>Export selected Excel</button></>}</>}
  </div>
  {error&&<p className="error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  {blocked?<div role="status"><p>The table was cleared because its session or authorization scope changed.</p><button onClick={()=>{setError('');setBlocked(false);}}>Reload permitted rows</button></div>:<Cells.Provider value={context}><div className="table-scroll"><DataTable ref={ref} ajax={ajax} options={options} className="display compact">
   {selectable&&<Column title="Select" data={null} options={{name:'_select',orderable:false,searchable:false}}>{(_value:unknown,_type:string,row:unknown)=><SelectCell row={row as T} label={String((row as Record<string,unknown>)[columns[0]?.key]||(row as T).id)+' · '+(row as T).id.slice(0,8)}/>}</Column>}
   {columns.map(column=><Column key={column.key} title={column.title} data={column.key} options={{name:column.key,orderable:column.orderable!==false,searchable:column.searchable!==false,visible:column.visible!==false}}>{(_value:unknown,_type:string,row:unknown)=><Cell field={column.key} row={row}/>}</Column>)}
  </DataTable></div></Cells.Provider>}
  <small>{selectable?'Rows, counts, filtering and exports use current server permissions. Selection clears when filters, scope or visible selected records change.':dataset==='accounts'?'Directory rows, counts and filtering require current administrator permissions.':dataset==='audit'?'Audit rows, counts and filtering use current category, matter and retained-event permissions.':'Registry rows require current matter administration scope; walls override assignments.'} {pauseRefresh?(dataset==='audit'?'Automatic refresh pauses while the audit ZIP is prepared; the server rechecks export permissions.':'Automatic table refresh pauses while you edit; server permission checks still apply.'):'Permissions refresh every 15 seconds.'}</small>
 </section>;
}
