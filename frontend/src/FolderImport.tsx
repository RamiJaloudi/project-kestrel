import {useEffect,useRef,useState} from 'react';
import type {VdrBatch} from './VdrImportPanel';
type Source={id:string;logical_key:string;file_name:string;bytes_hash:string;classification?:string;resource_type?:string;language?:string;governing_law?:string;superseded?:boolean};
type Row={file:File;path:string;key:string;previous:string;handling:string;type:string;language:string;law:string;hash:string;selected:boolean;state:string;message:string;importRowId?:string};
const types=['contract','licence','pricing','financial','legal_advice','client_upload','tracker','report'];
export default function FolderImport({matter,csrf,sources,batch,onImported,onBusyChange}:{matter:string;csrf:string;sources:Source[];batch?:VdrBatch|null;onImported:()=>Promise<void>;onBusyChange:(busy:boolean)=>void}){
 const input=useRef<HTMLInputElement>(null),stop=useRef(false);
 const [rows,setRows]=useState<Row[]>([]),[folder,setFolder]=useState(''),[wave,setWave]=useState('wave2'),[busy,setBusy]=useState(false),[loading,setLoading]=useState(false),[error,setError]=useState(''),[ignored,setIgnored]=useState(0),[synthetic,setSynthetic]=useState(false),[versions,setVersions]=useState(false);
 useEffect(()=>{input.current?.setAttribute('webkitdirectory','');input.current?.setAttribute('directory','');},[]);
 useEffect(()=>{if(batch)setWave(batch.wave);},[batch?.id]);
 useEffect(()=>{stop.current=true;setRows([]);setFolder('');setSynthetic(false);setVersions(false);setError('');},[matter]);
 useEffect(()=>()=>{stop.current=true;},[]);
 function update(index:number,change:Partial<Row>){setRows(current=>current.map((r,i)=>i===index?{...r,...change}:r));}
 async function choose(files:FileList|null){
  if(!files)return;onBusyChange(true);setLoading(true);setError('');setRows([]);setSynthetic(false);setVersions(false);
  try{
   const all=Array.from(files),supported=all.filter(f=>/\.(pdf|docx|xlsx|xlsm|xbrl|xml|ixbrl|xhtml|html|htm|eml|txt|csv)$/i.test(f.name));
   if(supported.length>100||supported.reduce((n,f)=>n+f.size,0)>50*1024*1024)throw new Error('Choose a smaller folder: up to 100 documents / 50 MiB per import.');
   const manifest=all.find(f=>f.name==='manifest.json');let entries:Record<string,unknown>[]=[];
   if(manifest&&manifest.size<256*1024){try{const value=JSON.parse(await manifest.text());if(Array.isArray(value.documents))entries=value.documents;}catch{/* Optional metadata never blocks ordinary folder selection. */}}
   setFolder(all[0]?.webkitRelativePath.split('/')[0]||'Selected folder');setIgnored(all.length-supported.length);
   const next:Row[]=[];
   for(const file of supported){
    const metadata=entries.find(e=>e.file_name===file.name),path=file.webkitRelativePath||file.name;
    const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))).map(n=>n.toString(16).padStart(2,'0')).join('');
    const matches=batch?.rows.filter(r=>{const name=(r.mapped.file_name||'').replace(/\\/g,'/');return name===path||name===path.split('/').slice(1).join('/')||name===file.name;})||[];
    const imported=matches.length===1?matches[0]:undefined;
    const key=imported?.mapped.logical_key||(typeof metadata?.logical_key==='string'?metadata.logical_key:file.name.replace(/_v\d+_.*/i,'').replace(/\.[^.]+$/,'').replace(/[^A-Za-z0-9_-]/g,'_').slice(0,96));
    const old=sources.find(s=>s.logical_key===key&&!s.superseded);
    const handling=['ordinary','privileged','clean_team'].includes(String(metadata?.classification))?String(metadata?.classification):'ordinary';
    const same=old?.bytes_hash===hash;
    next.push({file,path,key,previous:old?.id||'',handling:old?.classification==='clean_team'||handling==='clean_team'?'clean_team':old?.classification==='privileged'?'privileged':handling,type:old?.resource_type==='legal_advice'?'legal_advice':types.includes(String(metadata?.resource_type))?String(metadata?.resource_type):'contract',language:['en','de'].includes(String(metadata?.language))?String(metadata?.language):'unknown',law:typeof metadata?.governing_law==='string'?metadata.governing_law.slice(0,80):'unconfirmed',hash,selected:!same&&file.size<=3*1024*1024,state:same?'done':file.size>3*1024*1024?'excluded':'ready',message:same?'Already in this matter':file.size>3*1024*1024?'Exceeds 3 MiB per file':''});
    const added=next[next.length-1];
    if(batch){
     if(!imported||imported.state==='quarantined'){added.selected=false;added.state='excluded';added.message=matches.length>1?'Ambiguous CSV filename; use unique paths':imported?'CSV row quarantined':'No matching CSV row';}
     else {added.importRowId=imported.id;const mappedType=imported.mapped.doc_type?.toLowerCase();if(types.includes(mappedType)&&old?.resource_type!=='legal_advice')added.type=mappedType;
      if(same){added.state='ready';added.selected=true;added.message='Same bytes — link CSV provenance without a new version';}}
    }
   }
   setRows(next);if(!next.length)setError('No supported documents found. Choose files from the supported formats listed below.');
  }catch(e){setError((e as Error).message);}finally{onBusyChange(false);setLoading(false);if(input.current)input.current.value='';}
 }
 async function importFolder(){
  const selected=rows.filter(r=>r.selected&&r.state!=='done'&&r.state!=='excluded');
  if(new Set(selected.map(r=>r.key)).size!==selected.length){setError('Two selected files have the same document ID. Open File details and give them distinct IDs, or import versions separately.');return;}
  if(selected.some(r=>!/^[A-Za-z0-9_-]{1,96}$/.test(r.key))){setError('Document IDs must contain 1–96 letters, digits, underscores or hyphens.');return;}
  setBusy(true);onBusyChange(true);setError('');stop.current=false;
  try{
   for(let index=0;index<rows.length;index++){
    if(stop.current)break;const row=rows[index];if(!row.selected||['done','excluded'].includes(row.state))continue;
    update(index,{state:'uploading',message:'Importing…'});
    try{
     const check=await fetch('/api/v1/workflow/documents?matter_id='+encodeURIComponent(matter),{cache:'no-store'});
     if(!check.ok)throw new Error('Could not verify current matter access.');const current:Source[]=await check.json();
     if(!row.importRowId&&current.some(s=>s.logical_key===row.key&&s.bytes_hash===row.hash)){update(index,{state:'done',message:'Already imported; no duplicate created'});continue;}
     const params=new URLSearchParams({matter_id:matter,file_name:row.file.name,logical_key:row.key,classification:row.handling,resource_type:row.type,clean_team_scope:row.handling==='clean_team'?'pricing':'',language:row.language,governing_law:row.law||'unconfirmed',wave,synthetic:'true'});if(row.previous)params.set('previous_id',row.previous);
     if(row.importRowId)params.set('import_row_id',row.importRowId);
     const response=await fetch('/api/v1/workflow/documents?'+params,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-CSRF-Token':csrf},body:row.file});const result=await response.json();
     if(!response.ok)throw new Error(result.detail||'Import denied');
     update(index,{state:'done',message:result.extraction_status==='ready'?'Imported — ready for classification review':'Imported — OCR needed'});
    }catch(e){update(index,{state:'error',message:(e as Error).message});}
   }
   await onImported();
  }catch(e){setError((e as Error).message);}finally{setBusy(false);onBusyChange(false);}
 }
 const pending=rows.filter(r=>r.selected&&!['done','excluded'].includes(r.state)),replacements=pending.filter(r=>r.previous);
 return <section className="card folder-import"><div className="section-heading"><div><h2>Add a folder of documents</h2><p>Choose a folder, check the list, then import into the selected matter.</p></div><span className="pill">1 Choose → 2 Review → 3 Import</span></div><input ref={input} type="file" multiple hidden onChange={e=>choose(e.target.files)}/><div className="folder-choose"><button className="primary" disabled={busy||loading||!matter} onClick={()=>input.current?.click()}>{loading?'Reading folder…':'Choose folder'}</button><span>{folder||'No folder selected'}</span><label>Delivery batch<select disabled={busy||!!batch} value={wave} onChange={e=>setWave(e.target.value)}><option value="wave1">Wave 1</option><option value="wave2">Wave 2</option><option value="manual">Other delivery</option></select></label></div><p className="folder-help">Includes subfolders. Supported: PDF, DOCX, XLSX, inert XLSM, XBRL / XML XHTML iXBRL, EML, text and CSV. Up to 100 documents / 50 MiB per folder, 3 MiB per file. Hidden or opaque new-format content requires declared clean-team handling. Email attachments remain staged for explicit separate intake; nothing is automatically ingested. Legacy XLS, MSG, PST and OST remain unsupported.</p>{error&&<p className="error" role="alert">{error}</p>}
 {rows.length>0&&<><div className="folder-summary"><b>{rows.length} documents</b><span>{rows.filter(r=>r.state==='done').length} already present / imported</span><span>{pending.length} selected to import</span>{ignored>0&&<span>{ignored} supporting or unsupported files excluded</span>}</div><div className="folder-table"><table><thead><tr><th>Import</th><th>Document</th><th>Version</th><th>Access</th><th>Status</th></tr></thead><tbody>{rows.map((r,i)=><tr key={r.path}><td><input type="checkbox" aria-label={'Import '+r.file.name} disabled={busy||['done','excluded'].includes(r.state)} checked={r.selected&&!['done','excluded'].includes(r.state)} onChange={e=>update(i,{selected:e.target.checked})}/></td><td><b>{r.file.name}</b><small>{r.path} · {(r.file.size/1024).toFixed(0)} KB</small><details><summary>File details</summary><div className="folder-details"><label>Document ID<input disabled={busy||!!r.importRowId||r.state==='done'} value={r.key} maxLength={96} onChange={e=>update(i,{key:e.target.value,previous:''})}/></label><label>Previous document<select disabled={busy||r.state==='done'} value={r.previous} onChange={e=>{const old=sources.find(s=>s.id===e.target.value);update(i,{previous:e.target.value,key:old?.logical_key||r.key});}}><option value="">New document</option>{sources.filter(s=>!s.superseded).map(s=><option key={s.id} value={s.id}>{s.file_name}</option>)}</select></label><label>Access restriction<select disabled={busy||r.state==='done'} value={r.handling} onChange={e=>update(i,{handling:e.target.value})}><option value="ordinary">Standard matter access</option><option value="privileged">Privileged</option><option value="clean_team">Clean team — pricing</option></select></label><label>Document type<select disabled={busy||r.state==='done'} value={r.type} onChange={e=>update(i,{type:e.target.value})}>{types.map(t=><option key={t}>{t}</option>)}</select></label><label>Language<select disabled={busy||r.state==='done'} value={r.language} onChange={e=>update(i,{language:e.target.value})}><option value="unknown">Not yet confirmed</option><option value="en">English</option><option value="de">German</option></select></label><label>Declared governing law<input disabled={busy||r.state==='done'} value={r.law} maxLength={80} onChange={e=>update(i,{law:e.target.value})}/></label></div></details></td><td>{r.previous?'New version of existing document':'New document'}</td><td>{r.handling==='ordinary'?'Standard':r.handling==='clean_team'?'Clean team — pricing':'Privileged'}</td><td><span role="status">{r.message||'Ready'}</span>{r.state==='error'&&<small>Other successful imports are retained.</small>}</td></tr>)}</tbody></table></div><div className="folder-confirm"><label><input type="checkbox" disabled={busy} checked={synthetic} onChange={e=>setSynthetic(e.target.checked)}/>I confirm these documents are synthetic.</label>{replacements.length>0&&<label><input type="checkbox" disabled={busy} checked={versions} onChange={e=>setVersions(e.target.checked)}/>I reviewed the {replacements.length} proposed version matches. Previous versions will be retained.</label>}<div className="api-links"><button className="primary" disabled={busy||!csrf||!pending.length||!synthetic||!!replacements.length&&!versions} onClick={importFolder}>{busy?'Importing documents…':'Import '+pending.length+' selected documents'}</button>{busy&&<button onClick={()=>{stop.current=true;}}>Stop after current document</button>}</div><p>Each file is saved separately. Review classification after import; analysis does not start automatically. Clean-team files require the correct named membership. Manifest details are suggestions; the server enforces access.</p></div></>}
 </section>;
}
