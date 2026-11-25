import {useEffect,useState} from 'react';
export type VdrRow={id:string;row_number:number;state:string;errors:string[];mapped:Record<string,string>;source_ids:string[]};
export type VdrBatch={id:string;wave:string;rows:VdrRow[];notice:string};
type Profile={id:string;name:string;source_system:string;version_number:number;columns:Record<string,string>;delimiter:string};

function readHeaders(text:string,delimiter:string){
 const result:string[]=[];let value='',quoted=false;
 for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){value+='"';i++;}else quoted=!quoted;}else if(c===delimiter&&!quoted){result.push(value);value='';}else if((c==='\n'||c==='\r')&&!quoted){break;}else value+=c;}
 result.push(value);return result;
}

export default function VdrImportPanel({matter,csrf,batch,onBatch,onBusyChange}:{matter:string;csrf:string;batch:VdrBatch|null;onBatch:(v:VdrBatch|null)=>void;onBusyChange:(v:boolean)=>void}){
 const [fields,setFields]=useState<Record<string,string>>({}),[required,setRequired]=useState<string[]>([]),[profiles,setProfiles]=useState<Profile[]>([]);
 const [text,setText]=useState(''),[fileName,setFileName]=useState(''),[delimiter,setDelimiter]=useState(','),[columns,setColumns]=useState<Record<string,string>>({}),[name,setName]=useState('VDR CSV mapping'),[system,setSystem]=useState('Synthetic VDR'),[wave,setWave]=useState('wave2'),[synthetic,setSynthetic]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const headers=text?readHeaders(text.replace(/^\uFEFF/,''),delimiter):[];
 async function request(path:string,body?:unknown){const r=await fetch('/api/v1/vdr-imports'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},body:body?JSON.stringify(body):undefined,cache:'no-store'});const v=await r.json();if(!r.ok)throw new Error(v.detail||'VDR import unavailable');return v;}
 useEffect(()=>{let live=true;setText('');setFileName('');setColumns({});onBatch(null);setError('');setSynthetic(false);
  if(matter)Promise.all([request('/fields?matter_id='+encodeURIComponent(matter)),request('/profiles?matter_id='+encodeURIComponent(matter))]).then(([f,p])=>{if(live){setFields(f.fields);setRequired(f.required);setProfiles(p);}}).catch(e=>{if(live)setError(e.message);});
  return()=>{live=false;};
 },[matter]);
 async function choose(file?:File){if(!file)return;onBatch(null);setError('');setSynthetic(false);if(file.size>262144){setError('Choose a CSV up to 256 KiB and 100 rows.');return;}
  const value=await file.text();setText(value);setFileName(file.name);const h=readHeaders(value.replace(/^\uFEFF/,''),delimiter),mapping:Record<string,string>={};
  Object.entries(fields).forEach(([k,label])=>{const found=h.find(x=>x.toLowerCase()===label.toLowerCase());if(found)mapping[k]=found;});
  if(!mapping.source_external_id&&mapping.doc_id)mapping.source_external_id=mapping.doc_id;setColumns(mapping);
 }
 async function stage(){setBusy(true);onBusyChange(true);setError('');try{
  const prior=Math.max(0,...profiles.filter(p=>p.name===name).map(p=>p.version_number));
  const p=await request('/profiles',{matter_id:matter,name,source_system:system,columns,delimiter,expected_previous_version:prior});
  setProfiles(v=>[...v.filter(x=>x.id!==p.id),p]);
  const b=await request('/batches',{profile_id:p.id,file_name:fileName,csv_text:text,wave,request_key:crypto.randomUUID(),synthetic});onBatch(b);
 }catch(e){setError((e as Error).message);}finally{setBusy(false);onBusyChange(false);}}
 return <section className="card vdr-import-panel"><div className="section-heading"><div><h2>VDR metadata import</h2><p>Optional: map a vendor CSV, review its rows, then choose the document folder below.</p></div><span className="pill">1 Map CSV → 2 Check rows → 3 Add folder</span></div>
 <div className="vdr-import-controls"><label>Vendor metadata CSV<input type="file" accept=".csv,text/csv" disabled={busy} onChange={e=>void choose(e.target.files?.[0])}/></label><label>Separator<select disabled={busy} value={delimiter} onChange={e=>{setDelimiter(e.target.value);setColumns({});onBatch(null);}}><option value=",">Comma</option><option value=";">Semicolon</option><option value={'\t'}>Tab</option></select></label><label>Delivery<select value={wave} disabled={busy} onChange={e=>{setWave(e.target.value);onBatch(null);}}><option value="wave1">Wave 1</option><option value="wave2">Wave 2</option><option value="manual">Other delivery</option></select></label></div>
 {text&&<><div className="vdr-import-controls"><label>Mapping name<input value={name} disabled={busy} maxLength={96} onChange={e=>setName(e.target.value)}/></label><label>Source system<input value={system} disabled={busy} maxLength={96} onChange={e=>setSystem(e.target.value)}/></label><label>Reuse saved mapping<select disabled={busy} value="" onChange={e=>{const p=profiles.find(x=>x.id===e.target.value);if(p){setName(p.name);setSystem(p.source_system);setColumns(p.columns);setDelimiter(p.delimiter);onBatch(null);}}}><option value="">Select a version…</option>{profiles.map(p=><option key={p.id} value={p.id}>{p.name} · v{p.version_number}</option>)}</select></label></div>
 <div className="vdr-mapping-grid">{Object.entries(fields).filter(([key])=>required.includes(key)||key==='doc_id').map(([key,label])=><label key={key}>{label}{required.includes(key)?' *':''}<select disabled={busy} value={columns[key]||''} onChange={e=>{setColumns(v=>{const n={...v};if(e.target.value)n[key]=e.target.value;else delete n[key];return n;});onBatch(null);}}><option value="">{required.includes(key)?'Choose CSV column':'Generate stable key'}</option>{headers.map(h=><option key={h}>{h}</option>)}</select></label>)}</div>
 <details><summary>Optional title, dates, workstream and tracker columns</summary><p>These values are retained as metadata/proposals. Importing a row does not assign a reviewer, confirm a finding or release anything.</p><div className="vdr-mapping-grid">{Object.entries(fields).filter(([k])=>!required.includes(k)&&k!=='doc_id').map(([k,label])=><label key={k}>{label}<select value={columns[k]||''} disabled={busy} onChange={e=>{setColumns(v=>{const n={...v};if(e.target.value)n[k]=e.target.value;else delete n[k];return n;});onBatch(null);}}><option value="">Not mapped</option>{headers.map(h=><option key={h}>{h}</option>)}</select></label>)}</div></details>
 <label className="remember-option"><input type="checkbox" checked={synthetic} disabled={busy} onChange={e=>setSynthetic(e.target.checked)}/>This CSV contains synthetic data only.</label><button className="primary" disabled={busy||!synthetic||!required.every(k=>columns[k])||name.length<3||system.length<2} onClick={()=>void stage()}>{busy?'Checking CSV…':'Save mapping & check rows'}</button></>}
 {error&&<p className="error" role="alert">{error}</p>}
 {batch&&<div className="vdr-preview"><p role="status"><strong>{batch.rows.filter(r=>r.state!=='quarantined').length} ready · {batch.rows.filter(r=>r.state==='quarantined').length} quarantined</strong>. Choose the matching folder below. Valid rows supply stable document keys; errors must be corrected in a new CSV batch.</p><div className="folder-table"><table><thead><tr><th>Row</th><th>File / document key</th><th>Source / index / folder</th><th>Result</th></tr></thead><tbody>{batch.rows.map(r=><tr key={r.id}><td>{r.row_number}</td><td>{r.mapped.file_name}<small>{r.mapped.logical_key}</small></td><td>{r.mapped.source_external_id} · {r.mapped.vdr_index}<small>{r.mapped.folder_path}</small></td><td>{r.errors.length?r.errors.join(', '):r.state}</td></tr>)}</tbody></table></div><p className="muted">{batch.notice}</p><button onClick={()=>onBatch(null)}>Use folder import without this CSV</button></div>}
 </section>;
}
