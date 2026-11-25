import {useState} from 'react';
export default function ReportCoverage({report}:{report:string}){
 const [rows,setRows]=useState<{item_id:string;revision:number;recorded_status:string;checklist_hash:string}[]|null>(null),[error,setError]=useState('');
 async function load(){setError('');try{const r=await fetch('/api/v1/checklist-records/reports/'+report+'/coverage',{cache:'no-store'});const v=await r.json();if(!r.ok)throw new Error(v.detail||'Coverage unavailable');setRows(v.snapshots);}catch(e){setError((e as Error).message);}}
 return <details><summary>Internal checklist coverage captured for this report</summary><p>Exact recorded decisions from generation. Later coverage does not rewrite this version. This metadata is excluded from external report text.</p><button onClick={()=>void load()}>Load captured coverage</button>{error&&<p role="alert">{error}</p>}{rows?.length===0&&<p>No captured coverage references. Legacy reports are not backfilled; this does not establish complete or missing diligence.</p>}{rows?.map((r,i)=><p key={i}>{r.item_id} · revision {r.revision} · <b>{r.recorded_status.replace(/_/g,' ')}</b></p>)}</details>;
}
