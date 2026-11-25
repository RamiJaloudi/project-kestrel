import KestrelDataTable,{type TableColumn} from './KestrelDataTable';

export type RegistryHistoryRow={id:string;matter_id:string;kind:string;rationale:string;actor_id:string;target_id:string|null;occurred_at:number;revision:number};
const utc=(value:number)=>{const date=new Date(value*1000);return Number.isFinite(date.getTime())?date.toISOString().replace('T',' ').replace('.000Z',' UTC'):'Unavailable';};
export default function RegistryHistoryDataTable({matter,csrf,refreshKey,paused,onDenied,onStale}:{matter:string;csrf:string;refreshKey:number;paused:boolean;onDenied:()=>void;onStale:(message:string)=>void}){
 const columns:TableColumn<RegistryHistoryRow>[]=[
  {key:'revision',title:'Revision'},
  {key:'kind',title:'Event'},
  {key:'rationale',title:'Rationale',render:row=><details><summary>{Array.from(row.rationale).length>100?Array.from(row.rationale).slice(0,100).join('')+'…':row.rationale}</summary><p>{row.rationale}</p></details>},
  {key:'occurred_at',title:'Time (UTC)',render:row=>utc(row.occurred_at)},
  {key:'actor_id',title:'Actor ID',visible:false,render:row=><span className="registry-reference">{row.actor_id}</span>},
  {key:'target_id',title:'Target ID',visible:false,render:row=><span className="registry-reference">{row.target_id??'—'}</span>},
  {key:'id',title:'Decision ID',visible:false,render:row=><span className="registry-reference">{row.id}</span>}
 ];
 return <><p>Retained matter-validation and assignment decisions. Viewing history records no approval or new assignment.</p><KestrelDataTable<RegistryHistoryRow> dataset="registry_history" matter={matter} csrf={csrf} columns={columns} refreshKey={refreshKey} initialOrder={{column:'revision',direction:'desc'}} selectable={false} pauseRefresh={paused} onDenied={onDenied} onStale={onStale}/></>;
}
