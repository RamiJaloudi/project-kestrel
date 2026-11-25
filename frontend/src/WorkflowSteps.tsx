import {siteLinks,isAdminHost,isPublicSite,navigationUrl} from './siteLinks';
export function workflowLink(view:string,matter=new URLSearchParams(location.search).get('matter')||'',source='',unit?:number,start?:number,end?:number,historical=false){
 const query=new URLSearchParams({view});if(matter)query.set('matter',matter);if(source)query.set('source',source);
 if(unit!==undefined)query.set('unit',String(unit));if(start!==undefined)query.set('start',String(start));if(end!==undefined)query.set('end',String(end));
 if(historical)query.set('historical','true');
 return '/portal?'+query.toString();
}
export default function WorkflowSteps({organization='firm',active='',admin=false}:{organization?:string;active?:string;admin?:boolean}){
 const steps=organization==='firm'?[
  {name:'Validate matter',role:'Admin',url:siteLinks.admin+'/portal?view=Registry'},
  {name:'Ingest & classify',role:'Lawyer / named clean team',url:siteLinks.firm+workflowLink('Documents')},
  {name:'Analyze',role:'Legal SME',url:siteLinks.firm+workflowLink('Documents')},
  {name:'Review findings',role:'Lawyer',url:siteLinks.firm+workflowLink('Risk Review')},
  {name:'Approve release',role:'Independent lawyer / antitrust',url:siteLinks.firm+workflowLink('Release Desk')},
  {name:'View released output',role:'Client or bank',url:siteLinks.home+'/'}
 ]:[{name:'Choose matter',role:'Your assigned matters',url:workflowLink('Overview')},
     {name:'Read released findings',role:'Your organization audience',url:workflowLink(organization==='halden'?'Released Findings':'Commercial Findings')},
     {name:'Read workflow guide',role:'Resources',url:workflowLink('Resources')}];
 const current=steps.findIndex(s=>new URL(s.url,location.origin).searchParams.get('view')===active);
 return <details className="workflow-steps workflow-disclosure"><summary><strong>{admin?'Workflow & approval roles':'Workflow guide'}</strong><small>{current>=0?'Step '+(current+1)+' of '+steps.length:steps.length+' steps · roles and handoffs'}</small></summary><div className="workflow-body"><div className="section-heading"><span>Choose a step to continue</span><a href={organization==='firm'?siteLinks.firm+workflowLink('Resources'):workflowLink('Resources')}>Full guide</a></div><ol>{steps.map((s,i)=><li key={s.name}><a href={s.url} aria-current={current===i?'step':undefined}><b>{i+1}. {s.name}</b><small>{s.role}</small></a></li>)}</ol></div></details>;
}
