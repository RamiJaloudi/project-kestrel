import BrandMark from './BrandMark';
import {portals,siteLinks,isAdminHost,isHomeHost,isPublicSite,useSiteConfiguration} from './siteLinks';
import FinancialWorkspace from './FinancialWorkspace';
import DisclosuresWorkspace from './DisclosuresWorkspace';
import ChecklistWorkspace from './ChecklistWorkspace';
import TrackerExchange from './TrackerExchange';
import ActionCenter from './ActionCenter';
import ProfileMenu from './ProfileMenu';
import React, {useEffect, useState} from 'react';
import GovernancePreview from './GovernancePreview';
import Administration from './Administration';
import DiligenceWorkspace from './DiligenceWorkspace';
import Resources from './Resources';
import AuditWorkspace from './AuditWorkspace';
import PolicyWorkspace from './PolicyWorkspace';
import PortalHome from './PortalHome';
import WorkflowSteps from './WorkflowSteps';
import WorkflowWorkspace from './WorkflowWorkspace';
import MatterWorkspace from './MatterWorkspace';
import ReportsWorkspace from './ReportsWorkspace';
import QuestionsWorkspace from './QuestionsWorkspace';
import CollaborationWorkspace from './CollaborationWorkspace';
import CleanTeamWorkspace from './CleanTeamWorkspace';
import ClientUploadsWorkspace from './ClientUploadsWorkspace';
import LifecycleWorkspace from './LifecycleWorkspace';

const AgentRegistryWorkspace=React.lazy(()=>import('./AgentRegistryWorkspace'));
const DDRRunsWorkspace=React.lazy(()=>import('./DDRRunsWorkspace'));
const IntelligenceWorkspace=React.lazy(()=>import('./IntelligenceWorkspace'));
const ReviewTasksWorkspace=React.lazy(()=>import('./ReviewTasksWorkspace'));
const apiGroups = ['auth','portal','admin','governance','validation','client-matter-validations','ethical-walls','document-authorizations','oauth'];
type Identity = {id:string; organization:string; roles:string[];username:string};
const secure = location.protocol === 'https:';

function ApiLinks(){return <div className="api-links"><a href="/docs" target="_blank" rel="noreferrer">Swagger · all APIs</a>{apiGroups.map(g=><a key={g} href={'/docs/'+g} target="_blank" rel="noreferrer">{g} API</a>)}</div>}

export default function App(){
 const siteValid=useSiteConfiguration();
 const designPreview = !isPublicSite&&location.pathname === '/preview';
 const portal = portals.find(p=>p.host===location.hostname) || portals[1];
 const isHub = location.pathname==='/' && isHomeHost;
 const [identity,setIdentity]=useState<Identity|null>(null);
 const [username,setUsername]=useState(''); const [password,setPassword]=useState('');
 const [remember,setRemember]=useState(false),[savedUsername,setSavedUsername]=useState(false);
 const [csrf,setCsrf]=useState(''); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
 const [screen,setScreen]=useState(()=>new URLSearchParams(location.search).get('view')||'Overview');
 function navigate(view:string){
  const url=new URL(location.href);url.searchParams.set('view',view);
  for(const key of ['source','finding','revision_id','unit','start','end','historical','tab','report','release','section'])url.searchParams.delete(key);
  history.pushState(null,'',url);setScreen(view);
 }
 useEffect(()=>{const back=()=>setScreen(new URLSearchParams(location.search).get('view')||'Overview');window.addEventListener('popstate',back);return()=>window.removeEventListener('popstate',back);},[]);
 const [collapsed,setCollapsed]=useState(()=>window.matchMedia('(max-width:760px)').matches); const [checking,setChecking]=useState(true);
 useEffect(()=>{
  if(isHub||designPreview){setChecking(false);return;}
  let active=true;
  Promise.all([
   fetch('/api/v1/auth/preferences',{credentials:'same-origin'}).then(r=>r.ok?r.json():{username:'',remember_me:false}),
   fetch('/api/v1/auth/session',{method:'POST',credentials:'same-origin'}).then(r=>{if(r.status===401)return null;if(!r.ok)throw new Error('Session restoration denied. Sign in again.');return r.json();})
  ]).then(([preference,session])=>{
   if(!active)return;
   if(preference.username){setUsername(v=>v||preference.username);setRemember(true);setSavedUsername(true);}
   if(session){setIdentity(session.identity);setCsrf(session.csrf_token);setUsername(v=>v||session.identity.username);}
  }).catch(e=>{if(active)setError(e.message||'API unavailable. Start the local server.');}).finally(()=>{if(active)setChecking(false);});
  return()=>{active=false;};
 },[]);
 async function signIn(e:React.FormEvent<HTMLFormElement>){e.preventDefault();
  // Read real form values so password-manager autofill works without React events.
  const fields=new FormData(e.currentTarget);
  const loginName=String(fields.get('username')||'');const loginPassword=String(fields.get('password')||'');
  const rememberMe=fields.has('remember_me');
  setBusy(true);setError('');try{
   const r=await fetch('/api/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({username:loginName,password:loginPassword,remember_me:rememberMe})});
   if(!r.ok)throw new Error(r.status===429?'Too many attempts. Retry in 15 minutes.':'Login denied. Check credentials and organization portal.');
   setCsrf((await r.json()).csrf_token);const me=await fetch('/api/v1/auth/me');if(!me.ok)throw new Error('Session unavailable. Use HTTPS and allow this site’s cookie.');
   setUsername(loginName);setRemember(rememberMe);setSavedUsername(rememberMe);setIdentity(await me.json());
  }catch(e){setError((e as Error).message);}finally{setPassword('');setBusy(false);}}
 async function forgetUsername(){setBusy(true);setError('');try{
  const r=await fetch('/api/v1/auth/preferences',{method:'DELETE',credentials:'same-origin'});
  if(!r.ok)throw new Error('Unable to forget saved username.');
  setUsername('');setRemember(false);setSavedUsername(false);
 }catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function signOut(){setBusy(true);setError('');try{const r=await fetch('/api/v1/auth/logout',{method:'POST',headers:{'X-CSRF-Token':csrf}});if(!r.ok)throw new Error('Sign in again to renew your CSRF token before signing out.');setIdentity(null);setCsrf('');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 if(siteValid===null)return <main className="hub"><p>Checking portal configuration…</p></main>;
 if(!siteValid)return <main className="hub"><p>Portal configuration unavailable.</p></main>;
 if(designPreview && isAdminHost) return <Administration csrf="" preview onExit={()=>{location.href=siteLinks.admin+'/portal';}}/>;
 if(identity && isAdminHost) return <Administration csrf={csrf} roles={identity.roles} accountId={identity.id} profile={<ProfileMenu identity={identity} csrf={csrf} onCsrfChanged={setCsrf}/>} onExit={()=>csrf?signOut():setIdentity(null)}/>;
 if(isHub)return <PortalHome/>;
 const matterView=!!identity&&!designPreview&&portal.org==='firm'&&identity.roles.some(r=>['firm_lawyer','legal_sme','antitrust_counsel'].includes(r))&&['Overview','Risk Review','Diligence Trackers'].includes(screen);
 const workingView=['Overview','Documents','Risk Review','Release Desk','Legal Governance','Released Findings','Commercial Findings'].includes(screen)||(portal.org!=='firm'&&screen==='Reports');
 const navigation=portal.org==='firm'?['Overview','Documents','Tasks & assignments','Risk Review','Action Center','Diligence Trackers','DD Checklist','Reports & Board Pack','DDR Runs','Disclosures','Financial Evidence','Review Intelligence','Questions','Collaboration','Uploads','Clean Team','Resources','Release Desk','Playbook Management','Signing & Retention','Audit']:portal.org==='halden'?['Overview','Released Findings','Reports','Trackers','Disclosures','Financial Evidence','Review Intelligence','Questions','Collaboration','Uploads','Clean Team','Resources','Audit']:['Overview','Commercial Findings','Reports','Trackers','Disclosures','Financial Evidence','Review Intelligence','Questions','Collaboration','Resources','Audit'];
 if(portal.org==='firm'&&identity?.roles.some(r=>['root_admin','legal_sme'].includes(r)))navigation.push('Agent Registry');
 return <main className={'layout '+portal.color+(collapsed?' sidebar-collapsed':'')}><aside><button className="sidebar-toggle" aria-label="Toggle sidebar" aria-expanded={!collapsed} onClick={()=>setCollapsed(!collapsed)}>{collapsed?"Menu":"Collapse menu"}</button><div className="brand"><BrandMark/></div><div className="sidetitle">{portal.name} portal</div>{(identity||designPreview)&&navigation.filter(n=>!['Action Center','Tasks & assignments'].includes(n)||designPreview||identity?.roles.some(r=>['firm_lawyer','legal_sme','antitrust_counsel'].includes(r))).map(n=><button key={n} className={'nav '+(screen===n?'selected':'')} onClick={()=>navigate(n)}>{n}</button>)}<div className="asidefoot"><a href={siteLinks.home+'/'}>All portals</a><br/><a href="/docs" target="_blank" rel="noreferrer">Swagger API explorer</a></div></aside><section className="content"><header><div><div className="eyebrow">{portal.name.toUpperCase()} / SYNTHETIC WORKSPACE</div><h1>{matterView?'Project Kestrel':(identity||designPreview)?screen:'Sign in to '+portal.name}</h1><p>{portal.description}</p></div>{identity&&<ProfileMenu identity={identity} csrf={csrf} onCsrfChanged={setCsrf}/>}</header>{identity&&<WorkflowSteps organization={portal.org} active={screen}/>} {error&&<p className="error" role="alert">{error}</p>}
 {!identity&&!designPreview?<section className="card login-card"><h2>Your organization account</h2>{!secure&&<p className="notice">Read-only preview. <a href={`https://${location.hostname}:8443/portal`}>Open secure sign-in</a> to authenticate.</p>}<p>Credentials are checked by the API. The portal hostname does not grant access.</p>{!isPublicSite&&<p><a href="/preview">View synthetic design preview without signing in</a></p>}<form id="portal-login" name="kestrel-login" method="post" action="/api/v1/auth/login" autoComplete="on" onSubmit={signIn}><label htmlFor="username">Username</label><input id="username" name="username" autoComplete="username" required maxLength={128} value={username} onChange={e=>setUsername(e.target.value)}/><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" required maxLength={256} value={password} onChange={e=>setPassword(e.target.value)}/><label className="remember-option" htmlFor="remember-login"><input id="remember-login" name="remember_me" type="checkbox" checked={remember} onChange={e=>setRemember(e.target.checked)}/>Remember username and stay signed in (30 days)</label><small>Your browser can save and fill your password.</small><div className="api-links"><button className="primary" disabled={busy||checking||!secure} type="submit">{busy?'Signing in…':'Sign in'}</button>{savedUsername&&<button type="button" disabled={busy||checking} onClick={forgetUsername}>Forget saved username</button>}</div></form>{isPublicSite?<p>Use the organization account provided by the demo owner.</p>:<p>Use CREATE_ACCOUNT.bat to provision a local account for this organization.</p>}<ApiLinks/></section>:<>
 {designPreview&&<div className="notice">STATIC DESIGN PREVIEW — no authenticated identity, real matter data, or server actions. <a href="/portal">Go to real sign-in</a></div>}{identity&&!designPreview&&portal.org==='firm'&&screen==='Tasks & assignments'?<React.Suspense fallback={<p role="status">Loading permitted review tasks…</p>}><ReviewTasksWorkspace csrf={csrf} identity={identity}/></React.Suspense>:identity&&!designPreview&&screen==='Agent Registry'?<React.Suspense fallback={<p role="status">Loading governed agent profiles…</p>}><AgentRegistryWorkspace csrf={csrf} identity={identity}/></React.Suspense>:identity&&!designPreview&&screen==='DDR Runs'?<React.Suspense fallback={<p role="status">Loading governed report runs…</p>}><DDRRunsWorkspace csrf={csrf} identity={identity}/></React.Suspense>:identity&&!designPreview&&screen==='Review Intelligence'?<React.Suspense fallback={<p role="status">Loading authorized intelligence…</p>}><IntelligenceWorkspace csrf={csrf} internal={portal.org==='firm'}/></React.Suspense>:identity&&!designPreview&&screen==='Financial Evidence'?<FinancialWorkspace csrf={csrf} internal={portal.org==='firm'}/>:identity&&!designPreview&&screen==='Disclosures'?<DisclosuresWorkspace identity={identity} csrf={csrf}/>:identity&&!designPreview&&screen==='DD Checklist'?<ChecklistWorkspace csrf={csrf} identity={identity}/>:identity&&!designPreview&&screen==='Trackers'?<TrackerExchange csrf={csrf} identity={identity}/>:identity&&!designPreview&&(screen==='Action Center'||screen==='Legal Governance')?<ActionCenter csrf={csrf} identity={identity}/>:identity&&!designPreview&&screen==='Signing & Retention'?<LifecycleWorkspace csrf={csrf} identity={identity}/>:identity&&!designPreview&&screen==='Uploads'?<ClientUploadsWorkspace csrf={csrf} internal={portal.org==='firm'}/>:identity&&!designPreview&&screen==='Clean Team'?<CleanTeamWorkspace csrf={csrf} identity={identity}/>:identity&&!designPreview&&screen==='Collaboration'?<CollaborationWorkspace csrf={csrf} identity={identity}/>:identity&&!designPreview&&screen==='Questions'?<QuestionsWorkspace csrf={csrf} internal={portal.org==='firm'}/>:identity&&!designPreview&&(screen==='Reports & Board Pack'||portal.org!=='firm'&&screen==='Reports')?<ReportsWorkspace csrf={csrf} identity={identity}/>:matterView&&identity?<MatterWorkspace csrf={csrf} mode={screen} identity={identity}/>:workingView&&identity&&!designPreview?<WorkflowWorkspace identity={identity} csrf={csrf} mode={screen}/>:screen==='Overview'?<><div className="metrics"><div><b>{identity?"Connected":"Design only"}</b><small>{identity?"Verified server session":"No authenticated session"}</small></div><div><b>{portal.name}</b><small>Organization boundary</small></div><div><b>Scoped</b><small>Access checked for each request</small></div></div><section className="card hub-details"><h2>Account and feature status</h2><p>Organization: <strong>{identity?.organization||portal.org}</strong></p><p>Roles: {identity?.roles.join(', ')||'No signed-in account'}</p><p className="mono">Account: {identity?.id||"Not authenticated"}</p><p>Choose Documents to ingest or read permitted sources, Risk Review for lawyer decisions, and Reports for versioned audience packages. Review Intelligence groups only the records you may currently access. Each workspace shows its own permitted data and workflow controls.</p><ApiLinks/></section></>:screen==='Resources'?<Resources preview={designPreview}/>:screen==='Audit'?<AuditWorkspace csrf={csrf} accountId={identity?.id} preview={designPreview}/>:screen==='Playbook Management'?<PolicyWorkspace csrf={csrf} preview={designPreview}/>: (screen==='Diligence Trackers'||screen==='Reports & Board Pack')?<DiligenceWorkspace reports={screen==='Reports & Board Pack'}/>:screen==='Legal Governance'?<><div className="notice">DESIGN PREVIEW ONLY — actions below do not call the governance API.</div><GovernancePreview/></>:<section className="card hub-details"><span className="tag">Not implemented</span><h2>{screen}</h2><p>{portal.org==='castlegate'?'Only approved, explicitly released commercial artifacts will be eligible here. Legal advice and original source documents are excluded.':portal.org==='halden'?'Only explicitly released client material will be eligible here. Named clean-team membership alone will not grant general source access.':'This workflow will be added in a later verified sprint. No document, approval, release or audit record is created by this page.'}</p><p>The server keeps unfinished workflows closed. There is no fabricated live data.</p><ApiLinks/></section>}
 </>}</section></main>;
}







