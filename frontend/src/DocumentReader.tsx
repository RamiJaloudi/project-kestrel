import RedactionPanel,{type Removal} from './RedactionPanel';
import ContentLabels from './ContentLabels';
import ReaderTiming from './ReaderTiming';
import {useEffect,useId,useRef,useState} from 'react';



export type ReaderTarget={id:string;historical:boolean;kind?:'disclosure';taskId?:string;unit?:number;start?:number;end?:number};

type Unit={ocr?:boolean;number:number;locator:string;text:string};
type StagedAttachment={index:number;file_name:string;media_type:string;size:number;bytes_hash:string;state:'staged_not_ingested'};

type Sheet={name:string;state?:string;columns:number;rows:{number:number;unit:number;cells:{column:number;coordinate:string;text:string}[]}[]};

type Reader={can_classify_content?:boolean;id:string;file_name:string;version_number:number;bytes_hash:string;snapshot_hash:string;classification:string;language:string;governing_law:string;extraction_status:string;format:'pdf'|'word'|'excel'|'text';units:Unit[];blocks:{kind:string;unit:number;table?:number;cells?:string[]}[];sheets:Sheet[]};

function columnName(index:number):string{let value='';for(let n=index;n>0;n=Math.floor((n-1)/26))value=String.fromCharCode(65+(n-1)%26)+value;return value;}



export default function DocumentReader({target,onClose,csrf,embedded=false}:{target:ReaderTarget;onClose:()=>void;csrf?:string;embedded?:boolean}){

 const readerId=useId();const [view,setView]=useState(embedded?'evidence':'both');
 const dialog=useRef<HTMLDialogElement>(null),close=useRef<HTMLButtonElement>(null),evidence=useRef<HTMLDivElement>(null),documentPane=useRef<HTMLDivElement>(null);

 const [removals,setRemovals]=useState<Removal[]>([]);
 const [reader,setReader]=useState<Reader|null>(null),[error,setError]=useState(''),[selected,setSelected]=useState(target.unit||1),[sheet,setSheet]=useState(0),[zoom,setZoom]=useState(100),[search,setSearch]=useState('');
 const [attachments,setAttachments]=useState<StagedAttachment[]>([]);
 const [stageDownload,setStageDownload]=useState(false);

 const path=(target.kind==='disclosure'?'/api/v1/disclosures/artifacts/':'/api/v1/workflow/documents/')+encodeURIComponent(target.id),query='?historical='+target.historical;

 useEffect(()=>{

  if(embedded)return;
  const prior=document.activeElement as HTMLElement|null,overflow=document.body.style.overflow;

  document.body.style.overflow='hidden';dialog.current?.showModal();close.current?.focus();

  return()=>{document.body.style.overflow=overflow;prior?.focus();};

 },[]);

 useEffect(()=>{

  const controller=new AbortController();let active=true,checking=false;setAttachments([]);setStageDownload(false);

  async function load(initial=false){

   if(checking)return;checking=true;

   try{

    const response=await fetch(path+'/reader'+query,{cache:'no-store',credentials:'same-origin',signal:controller.signal});

    if(!response.ok)throw new Error(response.status===401?'Your session expired. Close the reader and sign in again.':response.status===403?'Document access is no longer permitted.':'The document reader is unavailable.');

    const value:Reader=await response.json();if(!active)return;

    if(target.kind!=='disclosure'&&/\.eml$/i.test(value.file_name)){
     const staged=await fetch(path+'/attachments'+query,{cache:'no-store',credentials:'same-origin',signal:controller.signal});
     if(!staged.ok)throw new Error('Email attachment staging is no longer available for this source.');
     const payload:{source_id:string;can_download:boolean;attachments:StagedAttachment[]}=await staged.json();
     if(payload.source_id!==value.id)throw new Error('Email staging does not match this source.');
     if(!active)return;setAttachments(payload.attachments);setStageDownload(payload.can_download);
    }else{setAttachments([]);setStageDownload(false);}

    setReader(current=>!current||current.snapshot_hash!==value.snapshot_hash?value:current);setError('');

    if(initial){const first=target.unit||value.units[0]?.number||1;setSelected(first);const index=value.sheets.findIndex(s=>s.rows.some(r=>r.unit===first));if(index>=0)setSheet(index);}

   }catch(e){if(active&&!controller.signal.aborted){setReader(null);setAttachments([]);setStageDownload(false);setError((e as Error).message);}}

   finally{checking=false;}

  }

  load(true);const timer=setInterval(()=>load(),15000);

  const visibility=()=>{if(document.visibilityState==='visible')load();};

  const pageHide=()=>{setReader(null);setAttachments([]);setStageDownload(false);};

  document.addEventListener('visibilitychange',visibility);window.addEventListener('pagehide',pageHide);

  return()=>{active=false;controller.abort();clearInterval(timer);document.removeEventListener('visibilitychange',visibility);window.removeEventListener('pagehide',pageHide);};

 },[path,query]);

 useEffect(()=>{

  evidence.current?.querySelector('[data-selected="true"]')?.scrollIntoView({block:'nearest'});

  documentPane.current?.querySelector('[data-selected="true"]')?.scrollIntoView({block:'nearest'});

 },[selected,reader,sheet]);

 const unit=reader?.units.find(u=>u.number===selected);

 const matches=reader?.units.filter(u=>search.trim()&&u.text.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))||[];

 function text(u:Unit){

  const chars=Array.from(u.text);let start=-1,end=-1;
  const spans=removals.filter(r=>r.unit===u.number).sort((a,b)=>a.start-b.start);
  if(spans.length){const parts=[];let cursor=0;for(const r of spans){if(r.start<cursor||r.end>chars.length)continue;parts.push(<span key={'keep'+cursor}>{chars.slice(cursor,r.start).join('')}</span>,<mark className="redaction-proposal" title="Proposed removal only; original bytes remain unchanged" key={'remove'+r.start}>{chars.slice(r.start,r.end).join('')}</mark>);cursor=r.end;}parts.push(<span key="rest">{chars.slice(cursor).join('')}</span>);return <>{parts}</>;}

  if(search.trim()){

   const index=u.text.toLocaleLowerCase().indexOf(search.trim().toLocaleLowerCase());

   if(index>=0){start=Array.from(u.text.slice(0,index)).length;end=start+Array.from(search.trim()).length;}

  }else if(u.number===target.unit){start=target.start??-1;end=target.end??-1;}

  return start>=0&&end>start&&end<=chars.length?<>{chars.slice(0,start).join('')}<mark>{chars.slice(start,end).join('')}</mark>{chars.slice(end).join('')}</>:u.text;

 }

 function selectUnit(number:number){setSelected(number);const index=reader?.sheets.findIndex(s=>s.rows.some(r=>r.unit===number))??-1;if(index>=0)setSheet(index);}

 const pdfPage=Number(unit?.locator.match(/^Page (\d+)$/)?.[1]||1);

 const cells=reader?.sheets[sheet];
 const evidenceOnly=!!reader&&target.kind!=='disclosure'&&/\.(xbrl|xml|ixbrl|xhtml|html|htm|eml)$/i.test(reader.file_name);

 const content=<>
  <div className="reader-shell"><header className="reader-header"><div><small>DOCUMENT READER</small><h2 id={readerId+'-title'}>{reader?reader.file_name:'Source evidence'}{reader&&<span> · v{reader.version_number}</span>}</h2>{reader&&<p>{reader.format.toUpperCase()} · {reader.classification} · {reader.language} · Governing law: {reader.governing_law}</p>}</div><button ref={close} className="reader-close" onClick={onClose} aria-label={embedded?'Close comparison pane':'Close document reader'}>Close ×</button></header>

  {error?<div className="reader-message error" role="alert">{error}</div>:!reader?<div className="reader-message" role="status">Loading authorized document…</div>:<>

   {reader.can_classify_content&&csrf&&<div className="reader-review-tools"><RedactionPanel source={target.id} unit={unit} csrf={csrf} historical={target.historical} onPreview={setRemovals}/><ContentLabels source={target.id} unit={unit} csrf={csrf} historical={target.historical}/></div>}
   {target.taskId&&csrf&&<ReaderTiming taskId={target.taskId} csrf={csrf} root={dialog}/>}<div className="reader-toolbar"><label>View<select value={evidenceOnly?'evidence':view} onChange={e=>setView(e.target.value)}><option value="evidence">Evidence text</option>{!evidenceOnly&&<><option value="original">Document</option><option value="both">Document + evidence</option></>}</select></label><label>Go to evidence<select aria-label="Evidence location" value={selected} onChange={e=>selectUnit(Number(e.target.value))}>{reader.units.map(u=><option key={u.number} value={u.number}>{u.locator}</option>)}</select></label><label>Find in document<input type="search" placeholder="Search original text" value={search} onChange={e=>setSearch(e.target.value)}/></label>{search&&<><small role="status">{matches.length} matching locations</small><button disabled={!matches.length} onClick={()=>selectUnit((matches.find(m=>m.number>selected)||matches[0]).number)}>Next match</button></>}<label>Text size<select value={zoom} onChange={e=>setZoom(Number(e.target.value))}>{[80,100,120,150].map(n=><option key={n} value={n}>{n}%</option>)}</select></label><a href={path+'/download'+query}>{target.kind==='disclosure'?'Download sanitized PDF':'Download original'}</a></div>

   {evidenceOnly&&<p className="reader-pdf-help">This format uses retained text evidence. Original XML, HTML and email layouts are not displayed.</p>}
   {attachments.length>0&&<details className="reader-review-tools"><summary>{attachments.length} staged email attachment{attachments.length===1?'':'s'} — not ingested</summary><p>Download a permitted attachment, then use Documents to submit it as a separate source and confirm its handling. Staging grants no additional access and creates no source or approval.</p>{!stageDownload&&<p>Download requires a current source with confirmed classification and permitted access.</p>}<ul>{attachments.map(item=><li key={item.index}><span>{item.file_name} · {item.size} bytes · {item.media_type}</span> {stageDownload&&<a href={path+'/attachments/'+item.index+'/download'+query}>Download staged attachment</a>}<details><summary>Integrity hash</summary><code>{item.bytes_hash}</code></details></li>)}</ul></details>}

   {reader.extraction_status!=='ready'&&<p className="notice reader-warning">OCR required. The original PDF can be viewed; missing extracted text is not analysis coverage.</p>}

   <div className="reader-panes" data-reader-view={evidenceOnly?'evidence':view}><div className="reader-original" ref={documentPane} style={{fontSize:zoom+'%'}}>

    {reader.format==='pdf'?<><iframe key={reader.id+'-'+pdfPage} className="reader-pdf" title={(target.kind==='disclosure'?'Sanitized transcript: ':'Original PDF: ')+reader.file_name} src={path+'/inline'+query+'#page='+pdfPage+'&view=FitH'} referrerPolicy="no-referrer"/><p className="reader-pdf-help">{target.kind==='disclosure'?'Sanitized PDF; not an original document.':'Original page '+pdfPage+'.'} The exact cited text is highlighted in the evidence pane. If your browser cannot display PDFs, use Download original.</p></>:

     reader.format==='excel'?<><div className="reader-sheet-tabs" role="tablist" aria-label="Workbook sheets">{reader.sheets.map((s,i)=><button key={s.name} role="tab" id={readerId+'-sheet-'+i} aria-selected={sheet===i} aria-controls={readerId+'-grid'} onClick={()=>{setSheet(i);if(s.rows[0])setSelected(s.rows[0].unit);}}>{s.name}{s.state&&s.state!=='visible'?' · '+s.state:''}</button>)}</div><div id={readerId+'-grid'} role="tabpanel" aria-labelledby={readerId+'-sheet-'+sheet} className="reader-grid"><table><caption>{cells?.name} · cell values from the immutable workbook</caption><thead><tr><th scope="col">Row</th>{Array.from({length:cells?.columns||0},(_,i)=><th key={i} scope="col">{columnName(i+1)}</th>)}</tr></thead><tbody>{cells?.rows.map(row=><tr key={row.number} data-selected={row.unit===selected} className={row.unit===selected?'reader-selected-row':''}><th scope="row"><button onClick={()=>setSelected(row.unit)} aria-label={'Read row '+row.number}>{row.number}</button></th>{Array.from({length:cells.columns},(_,i)=>{const cell=row.cells.find(c=>c.column===i+1);return <td key={i} title={cell?.coordinate}>{cell?.text||''}</td>;})}</tr>)}</tbody></table></div><p className="reader-pdf-help">Literal values and cell coordinates are shown. Formula expressions and cached results are unverified text; nothing is recalculated. Workbook formatting and charts are omitted.</p></>:

     <div className={'reader-paper '+(reader.format==='word'?'reader-word':'reader-text')}>{reader.blocks.map((block,i)=>{const u=reader.units.find(u=>u.number===block.unit);if(!u)return null;return <section key={i} data-selected={selected===u.number} className={selected===u.number?'reader-active-block':''}><button className="reader-locator" onClick={()=>setSelected(u.number)}>{u.locator}</button>{block.kind==='table_row'?<table><tbody><tr>{block.cells?.map((c,j)=><td key={j}>{c}</td>)}</tr></tbody></table>:<p>{text(u)}</p>}</section>;})}</div>}

   </div><div className="reader-evidence" ref={evidence} style={{fontSize:zoom+'%'}}><h3>{target.kind==='disclosure'?'Approved transcript evidence':'Original-language evidence'}</h3>{reader.units.some(u=>u.ocr)&&<p className="notice">Machine OCR transcript. Verify wording against the original PDF. Citations refer to this retained transcript and page.</p>}{reader.units.map(u=><article key={u.number} data-selected={selected===u.number} className={selected===u.number?'reader-active-block':''}><button className="reader-locator" onClick={()=>selectUnit(u.number)}>{u.locator}</button><pre>{u.text.trim()?text(u):'No extracted text. OCR is required.'}</pre></article>)}</div></div>

   <footer className="reader-footer"><span>Immutable version {reader.version_number} · SHA-256 {reader.bytes_hash}</span><span>Access rechecked every 15 seconds.</span></footer>

  </>}

  </div>

 </>;
 return embedded?<section className="document-reader reader-embedded" aria-labelledby={readerId+'-title'}>{content}</section>:<dialog className="document-reader" ref={dialog} aria-labelledby={readerId+'-title'} onCancel={e=>{e.preventDefault();onClose();}} onClick={e=>{if(e.target===dialog.current)onClose();}}>{content}</dialog>;

}

