import {useState} from 'react';
import KestrelDataTable,{type TableColumn} from './KestrelDataTable';

export type FindingRow={id:string;revision_id:string;revision:number;source_id:string;file_name:string;logical_key:string;version_number:number;summary:string;origin:string;rule_id:string|null;topic:string;severity:string;materiality:string;exposure:string;workflow_status:string;review_state:string;classification:string;owner_id:string|null;owner:string|null;due_on:string|null;created_at:number;historical:boolean};
export type FindingSelection=Pick<FindingRow,'id'|'revision_id'|'source_id'|'historical'>;
export type FindingRegister='all'|'risks'|'consents';
const label=(value:string)=>value.replace(/_/g,' ');
const topics=['change_of_control','assignment','exclusivity','non_compete','termination','liability_cap','governing_law','data_protection','other'];

export default function FindingsDataTable({matter,csrf,register,status,sourceId,historical,refreshKey,onChoose,onRead,onDenied}:{matter:string;csrf:string;register:FindingRegister;status:string;sourceId:string;historical:boolean;refreshKey:number;onChoose:(row:FindingSelection)=>void;onRead:(row:FindingSelection)=>void;onDenied:()=>void}){
 const [filters,setFilters]=useState<Record<string,string>>({});
 const columns:TableColumn<FindingRow>[]=[
  {key:'summary',title:'Finding',render:r=><><button className="finding-summary" type="button" aria-label={'Review finding · '+r.file_name+' · '+r.id.slice(0,8)} title={r.summary} onClick={()=>onChoose(r)}><span>{r.summary}</span><strong>Open review ›</strong></button><small>{label(r.origin)} · assessment v{r.revision}{r.historical?' · historical · read-only':''}</small></>},
  {key:'file_name',title:'Source',render:r=><div className="finding-source"><b>{r.file_name}</b><small>{r.logical_key} · v{r.version_number} · {label(r.classification)}</small></div>},
  {key:'topic',title:'Issue',render:r=>label(r.topic)},
  {key:register==='consents'?'exposure':'severity',title:register==='consents'?'Requirement':'Severity',render:r=>register==='consents'?label(r.exposure):<span className={'risk-severity '+r.severity}>{label(r.severity)}</span>},
  {key:'review_state',title:'Review / action',render:r=><>{label(r.review_state)}<small>{label(r.workflow_status)} · {label(r.materiality)}</small></>},
  {key:'owner',title:'Owner',render:r=>r.owner||'Unassigned / unavailable'},
  {key:'due_on',title:'Due',render:r=>r.due_on||'Unscheduled'},
  {key:'id',title:'Evidence',orderable:false,searchable:false,render:r=><button type="button" onClick={()=>onRead(r)}>Read source</button>}
 ];
 const choices:Record<string,string[]>={review_state:['candidate','reviewed','rejected'],topic:topics,severity:['critical','high','medium','low','information','unassessed'],materiality:['material','not_material','undetermined','unassessed'],exposure:['consent','notice','termination','none','unclear'],workflow_status:['open','in_progress','resolved'],origin:['ai_candidate','lawyer']};
 return <section aria-label="Findings register">
  <details><summary>Finding filters</summary><div className="source-work-columns">{Object.entries(choices).map(([key,values])=><label key={key}>{label(key)}<select value={filters[key]||''} onChange={e=>setFilters(previous=>({...previous,[key]:e.target.value}))}><option value="">All</option>{values.map(value=><option key={value} value={value}>{label(value)}</option>)}</select></label>)}</div><button type="button" onClick={()=>setFilters({})}>Clear finding filters</button></details>
  <KestrelDataTable<FindingRow> key={register} dataset="findings" matter={matter} csrf={csrf} columns={columns} filters={{finding_filters:{historical,register,status,...(sourceId?{source_id:sourceId}:{}),...Object.fromEntries(Object.entries(filters).filter(([,value])=>!!value))}}} refreshKey={refreshKey} onDenied={onDenied} allowExport/>
  <small>Selecting rows prepares an internal metadata export. Open one finding to review its exact version; approval and audience release remain separate. Missing findings do not establish completed review.</small>
 </section>;
}
