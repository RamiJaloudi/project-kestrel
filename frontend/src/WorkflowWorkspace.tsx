import {siteLinks,isAdminHost,isPublicSite,navigationUrl} from './siteLinks';
import CompareDocuments from './CompareDocuments';
import {useMatterSelection,selectPermittedMatter} from './matterSelection';
import React,{useEffect,useState,useRef} from 'react';

import {workflowLink} from './WorkflowSteps';

import DocumentReader,{type ReaderTarget} from './DocumentReader';

import FolderImport from './FolderImport';
import VdrImportPanel,{type VdrBatch} from './VdrImportPanel';
import SourceWorkPanel from './SourceWorkPanel';

type Identity={id:string;organization:string;roles:string[];username:string};

type Matter={id:string;name:string;client_number:string;matter_number:string};

type Source={id:string;matter_id:string;logical_key:string;file_name:string;version_number:number;classification:string;classification_confirmed:boolean;resource_type:string;wave:string;extraction_status:string;language:string;governing_law:string;snapshot_hash:string;bytes_hash:string;text_hash:string;extractor_version:string;units?:{number:number;locator:string;text:string}[];classification_requests?:{id:string;classification:string;resource_type:string;state:string;proposed_by:string;rationale:string}[]};

type Finding={id:string;revision_id:string;source_id:string;file_name:string;version_number:number;rule_id:string;summary:string;review_state:string;classification:string;playbook_hash:string;evidence:{unit:number;locator:string;start:number;end:number;quote:string}[]};

type Release={id:string;generated_report?:boolean;lineage_stale:boolean;title:string;summary:string;audience:string;released:boolean;content_hash:string;snapshot_hash:string;created_by:string;clean_team_required:boolean;antitrust_approved:boolean;references:{finding_id:string;public_reference:string}[];approvals?:{kind:string;actor_id:string;rationale:string}[]};

type Job={coverage?:{rule_id:string;status:string}[];id:string;state:string;attempts:number;document_version_id:string|null;error_code:string|null};

const InventoryDataTable=React.lazy(()=>import('./InventoryDataTable'));
const SOURCE_TYPES=['contract','licence','pricing','financial','legal_advice','client_upload','tracker','report'];

export default function WorkflowWorkspace({identity,csrf,mode}:{identity:Identity;csrf:string;mode:string}){

 const internal=identity.organization==='firm',legal=internal&&identity.roles.some(r=>['firm_lawyer','legal_sme','antitrust_counsel'].includes(r));

 const [matters,setMatters]=useState<Matter[]>([]),[matter,setMatter]=useMatterSelection();

 const [tableRevision,setTableRevision]=useState(0);
 const [sources,setSources]=useState<Source[]>([]),[selected,setSelected]=useState<Source|null>(null),[findings,setFindings]=useState<Finding[]>([]),[releases,setReleases]=useState<Release[]>([]),[jobs,setJobs]=useState<Job[]>([]);

 const ocrFingerprint=useRef('');

 const [ocrJobs,setOcrJobs]=useState<{id:string;source_id:string;state:string;result_source_id:string|null}[]>([]);

 const [reader,setReader]=useState<ReaderTarget|null>(null);
 const [vdrBatch,setVdrBatch]=useState<VdrBatch|null>(null);

 const [books,setBooks]=useState<{id:string;name:string}[]>([]),[book,setBook]=useState('');

 const [engine,setEngine]=useState('literal'),[ai,setAi]=useState<{enabled:boolean;key_configured:boolean;model:string;run_limit_cents:number;month_limit_cents:number;spent_estimate_cents:number;reserved_cents:number}|null>(null);

 useEffect(()=>{if(identity.roles.includes('legal_sme')||identity.roles.includes('root_admin'))request('/workflow/ai-status').then(setAi).catch(()=>{});},[]);

 const [error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false),[rationale,setRationale]=useState(''),[historical,setHistorical]=useState(()=>new URLSearchParams(location.search).get('historical')==='true');

 const [desiredLabel,setDesiredLabel]=useState('ordinary'),[desiredType,setDesiredType]=useState('contract');

 const [checked,setChecked]=useState<string[]>([]),[audience,setAudience]=useState('halden'),[title,setTitle]=useState(''),[summary,setSummary]=useState(''),[reference,setReference]=useState('Reviewed synthetic contract evidence');

 async function request(path:string,body?:unknown,method='POST'){

  const r=await fetch('/api/v1'+path,{method:body===undefined?'GET':method,headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});

  const value=await r.json();if(!r.ok)throw new Error(value.detail||'Workflow request denied');return value;

 }

 useEffect(()=>{let active=true;request('/workflow/matters').then((rows:Matter[])=>{if(!active)return;setMatters(rows);setMatter(selectPermittedMatter(rows));}).catch(e=>setError(e.message));return()=>{active=false;};},[]);

 async function refresh(){

  if(!matter)return;

  const query='?matter_id='+encodeURIComponent(matter),history='&historical='+historical;

  const output=await Promise.all([legal?request('/workflow/documents'+query+history):[],legal?request('/workflow/findings'+query+history):[],request('/workflow/releases'+query),legal?request('/workflow/playbooks'+query):[],legal?request('/jobs'+query+history):[]]);

  setTableRevision(v=>v+1);setSources(output[0]);setFindings(output[1]);setReleases(output[2]);setBooks(output[3]);setJobs(output[4]);if(!book&&output[3][0])setBook(output[3][0].id);

 }

 useEffect(()=>{setSources([]);setFindings([]);setReleases([]);setJobs([]);setSelected(null);setChecked([]);setBook('');if(matter)refresh().catch(e=>setError(e.message));},[matter,historical,mode]);

 useEffect(()=>{if(!matter||!legal)return;let alive=true;const timer=setInterval(async()=>{try{const [jobs,ocr]=await Promise.all([request('/jobs?matter_id='+encodeURIComponent(matter)+'&historical='+historical),request('/ocr?matter_id='+encodeURIComponent(matter))]);if(!alive)return;setJobs(jobs);setOcrJobs(ocr);const fingerprint=JSON.stringify(ocr);if(fingerprint!==ocrFingerprint.current){ocrFingerprint.current=fingerprint;if(ocr.some((j:{source_id:string;state:string})=>j.source_id===selected?.id&&j.state==='succeeded'))setSelected(null);await refresh();}}catch{}},5000);return()=>{alive=false;clearInterval(timer);};},[matter,legal,historical,selected?.id]);



 async function open(id:string){const result=await request('/workflow/documents/'+id+'?historical='+historical);setSelected(result);setDesiredLabel(result.classification);setDesiredType(result.resource_type);}

 useEffect(()=>{const query=new URLSearchParams(location.search),id=query.get('source');if(id&&matter&&legal){open(id).catch(e=>setError(e.message));if(query.has('unit'))setReader({id,historical,unit:Number(query.get('unit')),start:Number(query.get('start')),end:Number(query.get('end'))});}},[matter,historical]);

 async function act(fn:()=>Promise<unknown>){setBusy(true);setError('');setMessage('');try{await fn();await refresh();setMessage('Saved. The current permissions and workflow state were rechecked.');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}

 const disabled=busy||!csrf,reasonReady=rationale.trim().length>=5;

 const reviewed=findings.filter(f=>f.review_state==='reviewed');

 const params=new URLSearchParams(location.search),markUnit=Number(params.get('unit')),markStart=Number(params.get('start')),markEnd=Number(params.get('end'));

 useEffect(()=>{if(selected?.units&&markUnit>0)document.getElementById('unit-'+markUnit)?.scrollIntoView({block:'center'});},[selected,markUnit]);

 return <section className="workflow-workspace"><div className="card hub-details"><div className="section-heading"><h2>{mode==='Overview'?'Matter workflow':mode}</h2><button disabled={busy||!matter} onClick={()=>act(refresh)}>Refresh</button></div><label htmlFor="workflow-matter">Validated matter</label><select id="workflow-matter" disabled={busy} value={matter} onChange={e=>setMatter(e.target.value)}><option value="">Choose matter</option>{matters.map(m=><option key={m.id} value={m.id}>{m.client_number}-{m.matter_number}  ·  {m.name}</option>)}</select>{!matters.length&&<p>No validated, assigned and unwalled matters are available to this account.</p>}{error&&<p className="error" role="alert">{error}</p>}{message&&<p role="status">{message}</p>}{legal&&<label className="remember-option"><input type="checkbox" checked={historical} onChange={e=>setHistorical(e.target.checked)}/>Include permitted historical versions</label>}</div>

 {mode==='Overview'&&<section className="card hub-details"><h2>Next steps</h2><p>Signed in as {identity.username}. Permissions apply to this matter and account.</p><div className="metrics"><div><b>{legal?sources.length:'—'}</b><small>Visible source versions</small></div><div><b>{legal?findings.length:'—'}</b><small>Visible findings</small></div><div><b>{releases.filter(r=>r.released).length}</b><small>Visible released packages</small></div></div>{internal?<><ol><li><a href={workflowLink('Documents',matter)}>View Wave 1 documents and ingest Wave 2</a> as lawyer01, or cleanteam01 for pricing.</li><li><a href={workflowLink('Documents',matter)}>Confirm handling and authorize analysis</a> as sme01; use sme03 for named pricing scope.</li><li><a href={workflowLink('Risk Review',matter)}>Review exact cited evidence</a> as a lawyer.</li><li><a href={workflowLink('Release Desk',matter)}>Draft and independently approve an audience package</a>. Clean-team output also requires separate antitrust approval.</li><li><a href={siteLinks.home+'/'}>Open the client or bank portal</a> and verify the released audience view.</li></ol><p>Local files: <code>C:\Freshfields-Takehome\Synthetic_Data\Wave_2</code>. Wave 2 is for manual processing; it is not automatically imported.</p>{!legal&&<p>This administrative account does not have source-content authority. Use the named legal demo accounts for the document walkthrough.</p>}</>:<p><a href={workflowLink(identity.organization==='halden'?'Released Findings':'Commercial Findings',matter)}>Read packages approved for your organization</a>. Source documents and draft findings remain restricted.</p>}</section>}

 {mode==='Documents'&&legal&&<><CompareDocuments matter={matter} csrf={csrf}/><SourceWorkPanel key={matter} matter={matter} csrf={csrf} identity={identity} sources={sources} onOpen={(id,historical,taskId)=>setReader({id,historical,taskId})} onBusyChange={setBusy}/><VdrImportPanel matter={matter} csrf={csrf} batch={vdrBatch} onBatch={setVdrBatch} onBusyChange={setBusy}/><FolderImport key={matter+':'+(vdrBatch?.id||'folder')} matter={matter} csrf={csrf} sources={sources} batch={vdrBatch} onImported={refresh} onBusyChange={setBusy}/>

 <section className="card hub-details"><h2>Source documents</h2>{ocrJobs.map(j=><p key={j.id}>OCR: {j.state}{j.result_source_id&&<>  ·  <button onClick={()=>open(j.result_source_id!)}>Review new OCR transcript</button></>}</p>)}{matter&&<React.Suspense fallback={<p role="status">Loading authorized inventory table…</p>}><InventoryDataTable matter={matter} csrf={csrf} historical={historical} refreshKey={tableRevision} onRead={(id,readHistorical)=>{setReader({id,historical:readHistorical});}} onDenied={()=>{setSelected(null);setReader(null);setSources([]);}}/></React.Suspense>}</section>

 {selected&&<section className="card hub-details"><h2>{selected.file_name}  ·  v{selected.version_number}</h2><p>Language: {selected.language}  ·  Governing law: {selected.governing_law}  ·  Handling: {selected.classification}</p><small className="mono">SHA-256 {selected.bytes_hash}</small><p><a href={'/api/v1/workflow/documents/'+selected.id+'/download?historical='+historical}>Download permitted original</a></p>{selected.extraction_status!=='ready'&&<p className="notice">{selected.extraction_status==='ocr_review'?'OCR transcript is ready. Verify it against the original PDF before classification and analysis.':'OCR is required before analysis. No coverage is claimed for missing text.'}</p>}<label>Decision rationale<textarea value={rationale} maxLength={1000} onChange={e=>setRationale(e.target.value)}/></label><div className="api-links">{selected.extraction_status==='ocr_required'&&<button disabled={disabled||!selected.classification_confirmed} onClick={()=>act(()=>request('/ocr/'+selected.id,{}))}>Run offline OCR</button>}{selected.extraction_status==='ocr_review'&&<button disabled={disabled||!reasonReady} onClick={()=>act(async()=>{await request('/ocr/'+selected.id+'/verify',{text_hash:selected.text_hash,rationale});await open(selected.id);})}>Verify OCR text against original page</button>}<button disabled={disabled||!reasonReady||selected.classification_confirmed||selected.extraction_status==='ocr_review'} onClick={()=>act(async()=>{await request('/workflow/documents/'+selected.id+'/confirm',{snapshot_hash:selected.snapshot_hash,rationale});await open(selected.id);})}>Confirm intake classification</button><a href={workflowLink('Risk Review',matter,selected.id)}>Go to lawyer review</a></div><details><summary>Request an independently approved classification change</summary><div className="workflow-form-grid"><label>Requested handling<select value={desiredLabel} onChange={e=>setDesiredLabel(e.target.value)}><option value="ordinary">Ordinary</option><option value="privileged">Privileged</option><option value="clean_team">Clean team</option></select></label><label>Requested source type<select value={desiredType} onChange={e=>setDesiredType(e.target.value)}>{SOURCE_TYPES.map(t=><option key={t}>{t}</option>)}</select></label></div><button disabled={disabled||!reasonReady} onClick={()=>act(async()=>{await request('/workflow/documents/'+selected.id+'/classification-requests',{classification:desiredLabel,resource_type:desiredType,snapshot_hash:selected.snapshot_hash,rationale});await open(selected.id);})}>Submit classification request</button>{selected.classification_requests?.map(r=><div key={r.id}><p>{r.classification} / {r.resource_type}  ·  {r.state}  ·  {r.rationale}</p>{r.state==='pending'&&['approve','reject'].map(op=><button key={op} disabled={disabled||!reasonReady||r.proposed_by===identity.id} onClick={()=>act(async()=>{await request('/workflow/classification-requests/'+r.id+'/'+op,{rationale});await open(selected.id);})}>{op}</button>)}</div>)}</details><h3>3 Authorize first document analysis</h3><label>Published playbook<select value={book} onChange={e=>setBook(e.target.value)}><option value="">Choose published version</option>{books.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label><label>Analysis engine<select value={engine} onChange={e=>setEngine(e.target.value)}><option value="literal">Offline literal baseline</option><option value="openai" disabled={!ai?.enabled||!ai?.key_configured}>Live OpenAI  ·  configured key and processing approval required</option></select></label>{ai&&<p>Live AI budget: ${ai.run_limit_cents/100} per run / ${ai.month_limit_cents/100} per month. Estimated use ${(ai.spent_estimate_cents/100).toFixed(2)}, reserved ${(ai.reserved_cents/100).toFixed(2)}. {ai.enabled&&ai.key_configured?"Configured; source and environment restrictions still apply.":"Live provider disabled or not configured."}</p>}<button className="primary" disabled={disabled||!reasonReady||!book||!selected.classification_confirmed||selected.extraction_status!=='ready'||!identity.roles.includes('legal_sme')} onClick={()=>act(()=>request('/jobs',{playbook_id:book,document_version_id:selected.id,engine_name:engine,idempotency_key:'document-'+selected.id,rationale}))}>SME authorize & queue</button><p>Only a scoped Legal SME can authorize analysis. A completed version cannot be silently rerun; historical reruns require the separate impact workflow.</p>{jobs.filter(j=>j.document_version_id===selected.id).map(j=><div key={j.id}><p>Job {j.id}: <strong>{j.state}</strong>  ·  attempts {j.attempts}{j.error_code?'  ·  '+j.error_code:''}</p>{j.coverage?.length&&<><p>Per-risk review coverage. Not identified is not legal clearance.</p><table><thead><tr><th>Risk</th><th>Engine outcome</th></tr></thead><tbody>{j.coverage.map(c=><tr key={c.rule_id}><td>{c.rule_id}</td><td>{c.status.replace(/_/g,' ')}</td></tr>)}</tbody></table></>}</div>)}<h3>Immutable original-language text</h3>{selected.units?.map(u=><article className="source-unit" id={'unit-'+u.number} key={u.number}><h4>{u.locator}</h4><pre>{u.number===markUnit&&markEnd>markStart?<>{Array.from(u.text).slice(0,markStart).join('')}<mark>{Array.from(u.text).slice(markStart,markEnd).join('')}</mark>{Array.from(u.text).slice(markEnd).join('')}</>:u.text}</pre></article>)}</section>}</>}

 {mode==='Risk Review'&&legal&&<section className="card hub-details"><h2>4 Review source-bound candidates</h2><label>Attorney decision rationale<textarea maxLength={1000} value={rationale} onChange={e=>setRationale(e.target.value)}/></label>{findings.map(f=><article className="finding-row" key={f.id}><h3>{f.rule_id}  ·  {f.file_name} v{f.version_number}</h3><p>{f.summary}  ·  <strong>{f.review_state}</strong>  ·  {f.classification}</p>{f.evidence.map((e,i)=><p key={i}><a href={workflowLink('Documents',matter,f.source_id,e.unit,e.start,e.end,historical)} aria-haspopup="dialog" onClick={event=>{event.preventDefault();setReader({id:f.source_id,historical,unit:e.unit,start:e.start,end:e.end});}}>{e.locator}, characters {e.start}â€“{e.end}</a><br/><q>{e.quote}</q></p>)}<small>Playbook hash {f.playbook_hash}</small>{f.review_state==='candidate'&&<div className="api-links">{['reviewed','rejected'].map(decision=><button key={decision} disabled={disabled||!reasonReady} onClick={()=>act(()=>request('/workflow/findings/'+f.id+'/review',{decision,rationale}))}>{decision==='reviewed'?'Approve finding':'Reject finding'}</button>)}</div>}</article>)}{!findings.length&&<p>No findings are visible. Confirm and analyze a permitted source, then refresh.</p>}<a href={workflowLink('Release Desk',matter)}>Next: prepare the audience package</a></section>}

 {mode==='Release Desk'&&legal&&<form className="card hub-details" onSubmit={e=>{e.preventDefault();act(()=>request('/workflow/releases',{matter_id:matter,audience,title,summary,references:checked.map(id=>({finding_id:id,revision_id:findings.find(f=>f.id===id)?.revision_id,public_reference:reference}))}));}}><h2>5 Prepare an immutable audience package</h2><p>Choose reviewed findings and write the exact audience-safe summary. Source quotations are not copied automatically.</p>{reviewed.map(f=><label className="remember-option" key={f.id}><input type="checkbox" checked={checked.includes(f.id)} onChange={e=>setChecked(v=>e.target.checked?[...v,f.id]:v.filter(id=>id!==f.id))}/>{f.rule_id}  ·  {f.file_name}  ·  {f.classification}</label>)}<label>Audience<select value={audience} onChange={e=>setAudience(e.target.value)}><option value="halden">Halden</option><option value="castlegate">Castlegate</option></select></label><label>Package title<input required minLength={3} maxLength={160} value={title} onChange={e=>setTitle(e.target.value)}/></label><label>Audience-safe summary<textarea required minLength={10} maxLength={6000} value={summary} onChange={e=>setSummary(e.target.value)}/></label><label>Audience-safe citation label<input required minLength={3} maxLength={160} value={reference} onChange={e=>setReference(e.target.value)}/></label><button className="primary" disabled={disabled||!checked.length}>Create package for independent approval</button></form>}

 {(mode==='Release Desk'||!internal&&mode!=='Overview')&&<section className="card hub-details"><h2>{internal?'6 Approve or revoke exact packages':'Released audience packages'}</h2>{internal&&<label>Approval / revocation rationale<textarea maxLength={1000} value={rationale} onChange={e=>setRationale(e.target.value)}/></label>}{releases.map(r=><article key={r.id} className="finding-row"><h3>{r.title}</h3><p>{r.audience}  ·  <strong>{r.lineage_stale?'Source/finding changed â€” new release required':r.released?'Released':r.approvals?.some(a=>a.kind==='revoke')?'Revoked':'Awaiting approval'}</strong></p><p>{r.summary}</p><ul>{r.references.map(ref=><li key={ref.finding_id}>{ref.public_reference}</li>)}</ul>{internal&&<><small>Exact content hash {r.content_hash}</small>{r.generated_report&&<p><a href={workflowLink('Reports & Board Pack',matter)}>Open the complete report and annexes to review and approve</a></p>}{r.clean_team_required&&<p>Clean-team derived  ·  antitrust {r.antitrust_approved?'approved':'approval required'}</p>}<div className="api-links">{r.clean_team_required&&!r.antitrust_approved&&<button disabled={disabled||r.generated_report||!reasonReady||r.created_by===identity.id||!identity.roles.includes('antitrust_counsel')} onClick={()=>act(()=>request('/workflow/releases/'+r.id+'/antitrust',{content_hash:r.content_hash,snapshot_hash:r.snapshot_hash,rationale}))}>Antitrust approve sanitization</button>}<button disabled={disabled||!!r.generated_report&&!r.released||!reasonReady||!legal||(!r.released&&r.created_by===identity.id)} onClick={()=>act(()=>request('/workflow/releases/'+r.id+'/'+(r.released?'revoke':'approve'),{content_hash:r.content_hash,snapshot_hash:r.snapshot_hash,rationale}))}>{r.released?'Revoke package':'Independently approve release'}</button></div>{r.approvals?.map((a,i)=><p key={i}>{a.kind}: {a.rationale}</p>)}</>}</article>)}{!releases.length&&<p>No eligible packages are visible to this account and audience.</p>}</section>}

 {mode==='Legal Governance'&&legal&&<section className="card hub-details"><h2>Authorized analysis jobs</h2><table><thead><tr><th>Job</th><th>State</th><th>Attempts</th><th>Source</th></tr></thead><tbody>{jobs.map(j=><tr key={j.id}><td>{j.id}</td><td>{j.state}{j.error_code?' / '+j.error_code:''}</td><td>{j.attempts}</td><td>{j.document_version_id?<a href={workflowLink('Documents',matter,j.document_version_id)}>Open source version</a>:'Embedded synthetic examples'}</td></tr>)}</tbody></table><p>Document versions and historical candidates are retained. Full playbook-change impact snapshots, task decisions and approved historical reruns remain a separate phase.</p></section>}

 {internal&&!legal&&mode!=='Overview'&&<section className="card hub-details"><h2>Legal role required</h2><p>This account can administer configuration but has no source-content override. Follow the linked workflow using a scoped lawyer or Legal SME account.</p></section>}

 {reader&&<DocumentReader csrf={csrf} key={reader.id+':'+reader.unit+':'+reader.historical} target={reader} onClose={()=>setReader(null)}/>}

 </section>;

}

