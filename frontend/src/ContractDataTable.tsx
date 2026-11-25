import KestrelDataTable,{type TableColumn} from './KestrelDataTable';

type ContractSourceRow={id:string;file_name:string;logical_key:string;version_number:number;resource_type:string;classification:string;classification_confirmed:boolean;language:string;extraction_status:string};
type Props={matter:string;csrf:string;refreshKey:number;onChoose:(sourceId:string)=>void;onRead:(sourceId:string)=>void;onDenied:()=>void};
const label=(value:string)=>value.replace(/_/g,' ');
const languages:Record<string,string>={en:'English',de:'German',unknown:'Unknown'};
const filters={source_filters:{historical:false,contracts_only:true}};

// This register shares inventory identity and source evidence. Required filters
// reject incompatible saved configurations without changing their stored hashes.
export default function ContractDataTable({matter,csrf,refreshKey,onChoose,onRead,onDenied}:Props){
 const columns:TableColumn<ContractSourceRow>[]=[
  {key:'file_name',title:'Source',render:row=><><b>{row.file_name}</b><small>{row.logical_key}</small></>},
  {key:'version_number',title:'Version',render:row=>'v'+row.version_number},
  {key:'resource_type',title:'Source type',render:row=>label(row.resource_type)},
  {key:'classification',title:'Handling',render:row=>label(row.classification)},
  {key:'classification_confirmed',title:'Confirmed',render:row=>row.classification_confirmed?'Yes':'Pending'},
  {key:'language',title:'Language',render:row=>languages[row.language]||label(row.language)},
  {key:'extraction_status',title:'Text status',render:row=>label(row.extraction_status)},
  {key:'id',title:'Actions',orderable:false,searchable:false,render:row=><div className="api-links"><button type="button" onClick={()=>onChoose(row.id)} aria-label={'Open review for '+row.file_name}>Open review</button><button type="button" onClick={()=>onRead(row.id)} aria-label={'Read evidence for '+row.file_name}>Read evidence</button></div>}
 ];
 return <section aria-label="Contract source inventory" style={{minWidth:0}}>
  <p>Current contract and licence sources in your permitted scope. Open one source for fresh authorized review details.</p>
  <KestrelDataTable<ContractSourceRow> dataset="inventory" matter={matter} csrf={csrf} columns={columns} filters={filters} fixedSourceFilters={filters.source_filters} refreshKey={refreshKey} onDenied={onDenied} allowExport/>
  <small>Exports contain currently permitted source metadata. They do not approve findings, establish review coverage or release content to an audience.</small>
 </section>;
}
