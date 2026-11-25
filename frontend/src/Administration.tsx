import BrandMark from './BrandMark';
import {siteLinks,isAdminHost,isPublicSite,navigationUrl} from './siteLinks';
import FinancialGate from './FinancialGate';
import ReviewSlaWorkspace from './ReviewSlaWorkspace';
import ChecklistWorkspace from './ChecklistWorkspace';
import ActionCenter from './ActionCenter';
import AccountManagement from './AccountManagement';
import React from 'react';
import RegistryWorkspace from './RegistryWorkspace';
import Resources from './Resources';
import AuditWorkspace from './AuditWorkspace';
import PolicyWorkspace from './PolicyWorkspace';
import WorkflowSteps from './WorkflowSteps';
import AIProviderSettings from './AIProviderSettings';
import WallChecker from './WallChecker';
const AgentRegistryWorkspace=React.lazy(()=>import('./AgentRegistryWorkspace'));
export default function Administration({csrf,onExit,preview=false,roles=['root_admin'],profile,accountId}:{csrf:string;onExit:()=>void;preview?:boolean;roles?:string[];profile?:React.ReactNode;accountId?:string}){
 const registryAdmin=roles.includes('root_admin');
 const sections=registryAdmin?['Registry','Accounts','DD Checklist','Wall checker','Policies & playbooks','AI provider','Financial access','Audit reports','Resources']:roles.includes('conflicts_approver')?['Wall checker','Policies & playbooks','Audit reports','Resources']:['Resources','Audit reports',...(roles.includes('legal_sme')?['DD Checklist']:[])];
 if(roles.some(r=>['firm_lawyer','legal_sme','antitrust_counsel'].includes(r)))sections.push('Action Center');
 if(roles.some(r=>['root_admin','legal_sme'].includes(r)))sections.push('Review SLA','Agent Registry');
 const requestedArea=new URLSearchParams(location.search).get('view')||'';
 const area=sections.includes(requestedArea)?requestedArea:registryAdmin?'Registry':roles.includes('conflicts_approver')?'Wall checker':'Resources';
 return <main className="hub admin-workspace"><header><div className="admin-brand-heading"><BrandMark/><div><div className="eyebrow">ADMINISTRATION / SQL REGISTRY</div><h1>{(area==='Registry'||area==='Wall checker')?'Clients, matters & ethical walls':area==='AI provider'?'AI provider settings':area}</h1><p>Manage matter validation, access and approvals</p></div></div>{profile||<button className="primary" onClick={onExit}>{csrf?'Sign out':'Re-authenticate'}</button>}</header><WorkflowSteps admin/>{preview&&<p className="notice">READ-ONLY SYNTHETIC DESIGN PREVIEW. Example labels only; no authenticated identity or database records are loaded. <a href={siteLinks.admin+'/portal'}>Sign in to administer real local registry records</a>.</p>}<div className="admin-utilities"><span>Tools</span><a href="/docs/validation" target="_blank" rel="noreferrer">Registry API ↗</a><a href="/docs" target="_blank" rel="noreferrer">API explorer ↗</a><a href={siteLinks.home+'/'} target="_blank" rel="noreferrer">Portal Home ↗</a><button type="button" onClick={()=>location.reload()}>Refresh</button></div>{!csrf&&!preview&&<p className="notice">Re-authenticate to renew your in-memory CSRF token before changing records.</p>}
 <nav className="admin-section-tabs" aria-label="Administration sections">{sections.map(a=><a key={a} href={(preview?'/preview':'/portal')+'?view='+encodeURIComponent(a)} aria-current={area===a?'page':undefined} className={area===a?'active':''}>{a}</a>)}</nav>{area==='Agent Registry'?!preview&&accountId?<React.Suspense fallback={<p role="status">Loading governed agent profiles…</p>}><AgentRegistryWorkspace csrf={csrf} identity={{id:accountId,roles,organization:'firm'}}/></React.Suspense>:<p>Sign in to manage permitted agent profiles.</p>:area==='DD Checklist'?!preview&&accountId?<ChecklistWorkspace csrf={csrf} identity={{id:accountId,roles}}/>:<p>Sign in to manage permitted checklist scope.</p>:area==='Action Center'?!preview&&accountId?<ActionCenter csrf={csrf} identity={{id:accountId,roles}}/>:<p>Sign in to view permitted impact tasks.</p>:area==='Accounts'?<AccountManagement csrf={csrf} preview={preview}/>:area==='Wall checker'?<WallChecker csrf={csrf} preview={preview}/>:area==='Financial access'?!preview?<FinancialGate csrf={csrf}/>:<p>Sign in to configure financial access.</p>:area==='AI provider'?<AIProviderSettings csrf={csrf} preview={preview}/>:area==='Review SLA'?!preview&&accountId?<ReviewSlaWorkspace csrf={csrf} identity={{id:accountId,roles}}/>:<p>Sign in to configure approved operational SLA versions.</p>:area==='Resources'?<Resources preview={preview}/>:area==='Policies & playbooks'?<PolicyWorkspace csrf={csrf} preview={preview}/>:area==='Audit reports'?<AuditWorkspace csrf={csrf} accountId={accountId} preview={preview}/>:<RegistryWorkspace csrf={csrf} accountId={accountId} roles={roles} preview={preview}/>}<footer>Admin access does not override ethical walls or independent legal approval.</footer></main>;
}




