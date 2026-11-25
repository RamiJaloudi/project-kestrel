import {useEffect,useState} from 'react';

const local={home:'https://localhost:8443',admin:'https://admin.localhost:8443',firm:'https://firm.localhost:8443',halden:'https://client.localhost:8443',castlegate:'https://bank.localhost:8443'};
const approved={home:'https://portal.ramijaloudi.com',admin:'https://admin.portal.ramijaloudi.com',firm:'https://firm.portal.ramijaloudi.com',halden:'https://halden.portal.ramijaloudi.com',castlegate:'https://castlegate.portal.ramijaloudi.com'};
export const isPublicSite=Object.values(approved).some(url=>new URL(url).hostname===location.hostname);
export const siteLinks=isPublicSite?approved:local;
export const isAdminHost=location.hostname===new URL(siteLinks.admin).hostname;
export const isHomeHost=location.hostname===new URL(siteLinks.home).hostname||(!isPublicSite&&location.hostname==='127.0.0.1');
export const portals=[
 {host:new URL(siteLinks.admin).hostname,url:siteLinks.admin,name:'Administration',org:'firm',description:'Clients, matters and access controls',color:'firm',badge:'ADMIN'},
 {host:new URL(siteLinks.firm).hostname,url:siteLinks.firm,name:'Firm',org:'firm',description:'Review, track and release matter findings',color:'firm',badge:'LEGAL'},
 {host:new URL(siteLinks.halden).hostname,url:siteLinks.halden,name:'Halden',org:'halden',description:'Your released findings, reports and trackers',color:'client',badge:'CLIENT'},
 {host:new URL(siteLinks.castlegate).hostname,url:siteLinks.castlegate,name:'Castlegate',org:'castlegate',description:'Released commercial and financial findings',color:'bank',badge:'BANK'}
];

let bootstrap:Promise<boolean>|undefined;
export function useSiteConfiguration(){
 const [valid,setValid]=useState<boolean|null>(null);
 useEffect(()=>{
  if(!bootstrap)bootstrap=fetch('/site-config',{credentials:'same-origin',cache:'no-store'}).then(async response=>{
   // Compatibility with an already-running LOCAL API during a frontend-only
   // preview. Public and unknown hosts never use this fallback.
   if(!response.ok)return response.status===404&&!isPublicSite&&['localhost','127.0.0.1','testserver','admin.localhost','firm.localhost','client.localhost','bank.localhost'].includes(location.hostname);
   const value=await response.json();
   return value.mode===(isPublicSite?'PUBLIC_DEMO':'LOCAL')&&value.synthetic_only===true&&Object.entries(siteLinks).every(([key,url])=>value.links?.[key]===url);
  }).catch(()=>false);
  let active=true;bootstrap.then(value=>{if(active)setValid(value);});return()=>{active=false;};
 },[]);
 return valid;
}

// Call only for authored application navigation, never source/evidence URLs.
export function navigationUrl(value:string){
 for(const [key,prefix] of Object.entries(local))if(value===prefix||value.startsWith(prefix+'/'))return siteLinks[key as keyof typeof siteLinks]+value.slice(prefix.length);
 return value;
}
