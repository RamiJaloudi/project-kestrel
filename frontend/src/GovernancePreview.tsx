import React, {useMemo, useState} from 'react';

type Tab='Changes'|'Impact'|'Decision'|'History';
type Decision='pending'|'approved'|'rejected';
const changes=[
  {id:'COC-03',change:'Modified',before:'Detect direct change in ownership expressly covered by the contract.',after:'Also detect indirect control changes and ultimate ownership when the contract so provides.'},
  {id:'COC-09',change:'Added',before:'(No prior rule)',after:'Flag express deemed-assignment clauses that require consent for a qualifying change of control, subject to exceptions.'}
];
const docs=[
 {id:'DOC-001:v1',kind:'Ordinary contract',approved:1,released:1,ct:false},
 {id:'DOC-002:v2',kind:'German license / English law',approved:1,released:0,ct:false},
 {id:'DOC-003:v1',kind:'Clean-team source',approved:0,released:0,ct:true},
 {id:'DOC-004:v1',kind:'Assignment provision',approved:0,released:0,ct:false},
];
export default function App(){
 const [tab,setTab]=useState<Tab>('Changes');
 const [decision,setDecision]=useState<Decision>('pending');
 const [rationale,setRationale]=useState('');
 const [scope,setScope]=useState<'unrestricted'|'all'>('unrestricted');
 const [read,setRead]=useState(false);
 const [ack,setAck]=useState(false);
 const stats=useMemo(()=>({docs:docs.length, approved:docs.reduce((x,d)=>x+d.approved,0),released:docs.reduce((x,d)=>x+d.released,0),ct:docs.filter(d=>d.ct).length}),[]);
 return <main className="layout">
  <aside><div className="brand">KESTREL<span>UNOFFICIAL DEMO</span></div><div className="sidetitle">Firm workspace</div>
   {['Dashboard','Documents','AI Review','Release Desk','Playbook Management','Legal Governance','Audit Events'].map(x=><div className={'nav '+(x==='Legal Governance'?'selected':'')} key={x}>{x}</div>)}
   <div className="asidefoot">Offline UI preview only<br/>No real login or API connection</div>
  </aside>
  <section className="content">
   
   <header><div><div className="eyebrow">Project Kestrel / Freshfields-side synthetic shell</div><h1>Legal Governance Action Center</h1><p>Material playbook change review and reanalysis authorization</p></div><div className="notification" onClick={()=>{setRead(true)}} role="button" tabIndex={0} onKeyDown={e=>e.key==='Enter'&&setRead(true)}>🔔 {read?'Read':'1 new task'}</div></header>
   <div className="card"><div className="taskhead"><div><h2>Change of Control — German Contracts</h2><p>PB-COC-DE-001 · v1.2.0 → v1.3.0 · Material change</p></div><span className="tag">{decision==='pending'?'Requires SME decision':`Preview ${decision}`}</span></div>
   <div className="metrics"><div><b>{stats.docs}</b><small>Affected document versions</small></div><div><b>{stats.approved}</b><small>Approved findings</small></div><div><b>{stats.released}</b><small>Released artifacts</small></div><div><b>{stats.ct}</b><small>Clean-team restricted</small></div></div>
   <nav className="tabs">{(['Changes','Impact','Decision','History'] as Tab[]).map(t=><button key={t} className={tab===t?'active':''} onClick={()=>setTab(t)}>{t}</button>)}</nav>
   {tab==='Changes'&&<div className="panel"><h3>Exact rule-level comparison</h3>{changes.map(c=><article className="change" key={c.id}><div className="changehead"><strong>{c.id}</strong><span>{c.change}</span></div><div className="columns"><div><small>BEFORE / 1.2.0</small><p>{c.before}</p></div><div><small>AFTER / 1.3.0</small><p>{c.after}</p></div></div></article>)}</div>}
   {tab==='Impact'&&<div className="panel"><h3>Potentially affected scope</h3><p>Counts are computed from this tiny synthetic preview fixture. A real SME view must enforce matter and clean-team permissions before showing each record.</p><table><thead><tr><th>Document version</th><th>Classification</th><th>Approved</th><th>Released</th></tr></thead><tbody>{docs.map(d=><tr key={d.id}><td>{d.id}</td><td>{d.ct?'Restricted — gated':d.kind}</td><td>{d.approved}</td><td>{d.released}</td></tr>)}</tbody></table></div>}
   {tab==='Decision'&&<div className="panel"><h3>Legal SME determination</h3><p>This form is a UI interaction only. Real approval remains denied in the backend scaffold until a signed-in independent Legal SME and transactional snapshot validation are implemented.</p><label>Reanalysis scope</label><select disabled={decision!=='pending'} value={scope} onChange={e=>setScope(e.target.value as 'unrestricted'|'all')}><option value="unrestricted">Unrestricted documents only (recommended)</option><option value="all">All documents, including clean team (additional authorization required)</option></select><label>Rationale (mandatory)</label><textarea disabled={decision!=='pending'} value={rationale} onChange={e=>setRationale(e.target.value)} placeholder="Why should this playbook change trigger reanalysis of the specified documents?"/>
     {decision==='pending'?<div className="buttons"><button disabled={!rationale.trim()} onClick={()=>setDecision('approved')}>Preview approve</button><button className="secondary" disabled={!rationale.trim()} onClick={()=>setDecision('rejected')}>Preview reject</button></div>:<div className="success"><strong>Preview {decision}</strong><p>No server decision, queue job or audit record was created.</p><button onClick={()=>{setDecision('pending');setRationale('')}}>Reset preview</button></div>}
   </div>}
   {tab==='History'&&<div className="panel"><h3>Illustrative audit trail</h3><table><tbody><tr><td>playbook.version.published</td><td>v1.3.0 (synthetic)</td></tr><tr><td>impact.assessment.completed</td><td>{stats.docs} candidate versions</td></tr><tr><td>notification.created</td><td>SME inbox — unread until clicked</td></tr><tr><td>notification.state</td><td>{ack?'acknowledged':read?'read':'unread'}</td></tr></tbody></table><button className="secondary" onClick={()=>setAck(true)}>Preview acknowledge notification</button><p>Acknowledgement does not authorize reanalysis.</p></div>}
   </div>
   <p className="bottom">The actual production proposal requires real sessions, policy gates, PostgreSQL, exact immutable snapshot hashes, independent legal approval, queued jobs and auditing. None of those are implemented by this visual mock.</p>
  </section>
 </main>;
}
