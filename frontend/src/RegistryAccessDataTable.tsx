import KestrelDataTable,{type TableColumn} from './KestrelDataTable';

export type RegistryAccessRow={id:string;account_id:string;matter_id:string;username:string;organization:string;assigned:boolean;blocked:boolean;effective_blocked:boolean;active:boolean};
type Props={matter:string;csrf:string;accountId:string;refreshKey:number;locked:boolean;onChoose:(username:string)=>void;onDenied:()=>void;onStale:(message:string)=>void};
export default function RegistryAccessDataTable({matter,csrf,accountId,refreshKey,locked,onChoose,onDenied,onStale}:Props){
 const columns:TableColumn<RegistryAccessRow>[]=[
  {key:'username',title:'Account',render:row=><><b>{row.username}</b><small>{row.active?'Active account':'Inactive account'}</small></>},
  {key:'organization',title:'Employer'},
  {key:'assigned',title:'Assignment active',render:row=>row.assigned?'Yes':'No'},
  {key:'blocked',title:'Direct wall',render:row=>row.blocked?'Recorded':'None recorded'},
  {key:'effective_blocked',title:'Effective wall',render:row=>row.effective_blocked?'Blocked':'No current wall'},
  {key:'active',title:'Account state',visible:false,render:row=>row.active?'Active':'Inactive'},
  {key:'account_id',title:'Account ID',visible:false,render:row=><span className="registry-reference">{row.account_id}</span>},
  {key:'id',title:'Action',orderable:false,searchable:false,render:row=><button type="button" disabled={locked||row.account_id===accountId||row.matter_id!==matter} onClick={()=>onChoose(row.username)}>Look up target</button>}
 ];
 return <><p>Accounts with a previous assignment or direct-wall record. Active assignment is separate from effective access; walls still apply.</p><KestrelDataTable<RegistryAccessRow> dataset="registry_access" matter={matter} csrf={csrf} columns={columns} refreshKey={refreshKey} selectable={false} pauseRefresh={locked} onDenied={onDenied} onStale={onStale}/></>;
}
