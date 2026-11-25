import {useState} from 'react';
import KestrelDataTable,{type TableColumn} from './KestrelDataTable';

export type AccountMetadata={id:string;upn:string;display_name:string;employee_id:string;organization:string;roles:string[];active:boolean;revision:number};
export type AccountSelection=Pick<AccountMetadata,'id'|'revision'>;
type Props={csrf:string;refreshKey:number;disabled?:boolean;onChoose:(account:AccountSelection)=>void;onDenied:()=>void};
type Employer=''|'firm'|'halden'|'castlegate';
const employers:Record<string,string>={firm:'Freshfields',halden:'Halden',castlegate:'Castlegate'};
const label=(value:string)=>value.replace(/_/g,' ');

export default function AccountDirectoryDataTable({csrf,refreshKey,disabled=false,onChoose,onDenied}:Props){
 const [organization,setOrganization]=useState<Employer>(''),[active,setActive]=useState('all');
 const columns:TableColumn<AccountMetadata>[]=[
  {key:'display_name',title:'Display name',render:row=>row.display_name||'Name not set'},
  {key:'upn',title:'Account',render:row=><><b>{row.upn}</b><small>Profile revision {row.revision}</small></>},
  {key:'employee_id',title:'Employee ID'},
  {key:'organization',title:'Employer',render:row=>employers[row.organization]||row.organization},
  {key:'roles',title:'Roles',orderable:false,render:row=>row.roles.length?row.roles.map(label).join(', '):'No roles'},
  {key:'active',title:'Account state',render:row=>row.active?'Active':'Inactive'},
  {key:'id',title:'Action',orderable:false,searchable:false,render:row=><button type="button" disabled={disabled} aria-label={'Edit metadata for '+row.upn} onClick={()=>onChoose({id:row.id,revision:row.revision})}>Edit metadata</button>}
 ];
 return <section aria-label="Account directory" style={{minWidth:0}}>
  <div className="table-filter-row"><label>Employer<select disabled={disabled} value={organization} onChange={event=>setOrganization(event.target.value as Employer)}><option value="">All employers</option>{Object.entries(employers).map(([value,name])=><option key={value} value={value}>{name}</option>)}</select></label><label>Account state<select disabled={disabled} value={active} onChange={event=>setActive(event.target.value)}><option value="all">All accounts</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label></div>
  <KestrelDataTable<AccountMetadata> dataset="accounts" csrf={csrf} columns={columns} filters={{account_filters:{...(organization?{organization}:{}),...(active!=='all'?{active:active==='active'}:{})}}} refreshKey={refreshKey} onDenied={onDenied} selectable={false}/>
  <small>This directory edits names and employer-specific employee IDs. Roles, account activation and matter access retain their separate controls.</small>
 </section>;
}
