import {useEffect,useState} from 'react';
import AssetLibrary from './AssetLibrary';
import './asset-library.css';
type Guide={id:string;title:string;body:string;links?:{label:string;href:string}[];workbook_href:string;step_count:number;audience:string[];workflow_status:string};
export default function Resources({preview=false}:{preview?:boolean}){
 const [guides,setGuides]=useState<Guide[]>([]),[error,setError]=useState('');
 const [query,setQuery]=useState('');
 const [engines,setEngines]=useState<{name:string;status:string;mode:string}[]>([]);
 useEffect(()=>{if(!preview)fetch('/api/v1/resources/engines').then(async r=>{if(r.ok)setEngines(await r.json());}).catch(()=>{});},[preview]);
 useEffect(()=>{if(!preview)fetch('/api/v1/resources').then(async r=>{if(!r.ok)throw new Error('Resources access denied');setGuides(await r.json());}).catch(e=>setError(e.message));},[preview]);
 const matching=guides.filter(g=>(g.title+' '+g.body+' '+g.audience.join(' ')).toLowerCase().includes(query.trim().toLowerCase()));
 return <section className="card hub-details resources-workflows"><h2>Resources</h2><AssetLibrary preview={preview}/><h3>Workflow guides</h3><p>Download an Excel walkthrough with numbered actions, page links and expected results. Record completion, dates and notes in your copy. Submit approvals in the application.</p>{preview&&<p className="notice">Sign in for role-specific workflows. Restricted clean-team guidance requires active named membership.</p>}{error&&<p className="error" role="alert">{error}</p>}{!!guides.length&&<label className="resource-search">Find a workflow<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search tasks or roles"/></label>}{!preview&&!error&&!!guides.length&&!matching.length&&<p>No workflows match your search.</p>}{matching.map(g=><article className="resource-guide" key={g.id}><div className="resource-guide-heading"><div><h3>{g.title}</h3><small>{g.step_count} steps · {g.audience.join(', ')}</small></div><a className="primary-link resource-excel" href={g.workbook_href} download aria-label={'Download Excel workflow: '+g.title}>Excel workflow (.xlsx)</a></div><details><summary>Read guidance and open pages</summary><p>{g.body}</p><p className="muted">{g.workflow_status}</p>{g.links&&<ul>{g.links.map(link=><li key={link.href}><a href={link.href}>{link.label}</a></li>)}</ul>}<a href={'/api/v1/resources/'+g.id+'/download'}>Text guide (.md)</a></details></article>)}{!!engines.length&&<details className="resource-engine-status"><summary>Engine status</summary><table><thead><tr><th>Engine</th><th>Status</th><th>Details</th></tr></thead><tbody>{engines.map(e=><tr key={e.name}><td>{e.name}</td><td>{e.status}</td><td>{e.mode}</td></tr>)}</tbody></table></details>}</section>;
}

