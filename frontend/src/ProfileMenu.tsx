import React,{useEffect,useRef,useState} from 'react';

type Profile={id:string;upn:string;display_name:string;employee_id:string;organization:string;roles:string[];clean_team_scopes:{matter:string;scope:string}[];expires_at:number;session_stamp:string;authorization_stamp:string};
const employers:Record<string,string>={firm:'Freshfields',halden:'Halden Industries',castlegate:'Castlegate'};
export default function ProfileMenu({identity,csrf,onCsrfChanged}:{identity:{id:string;username:string};csrf:string;onCsrfChanged:(value:string)=>void}){
 const [profile,setProfile]=useState<Profile|null>(null),[error,setError]=useState(''),[notice,setNotice]=useState(''),[changing,setChanging]=useState(false),[busy,setBusy]=useState(false);
 const [unread,setUnread]=useState(0);
 const current=useRef<Profile|null>(null),details=useRef<HTMLDetailsElement>(null);
 useEffect(()=>{
  let active=true,inFlight=false;
  async function check(){
   if(inFlight||document.visibilityState==='hidden')return;inFlight=true;
   try{
    const r=await fetch('/api/v1/auth/profile',{credentials:'same-origin',cache:'no-store'});
    if(!active)return;
    if(r.status===401||r.status===403){location.reload();return;}
    if(!r.ok)throw new Error('Unable to verify the current account. Retry shortly.');
    const next:Profile=await r.json();if(!active)return;
    const previous=current.current;
    if(next.id!==identity.id||(previous&&(previous.session_stamp!==next.session_stamp||previous.authorization_stamp!==next.authorization_stamp))){location.reload();return;}
    current.current=next;setProfile(next);setError('');
    if(next.organization==='firm'&&next.roles.some(r=>['firm_lawyer','legal_sme','antitrust_counsel'].includes(r))){
     try{const notices=await fetch('/api/v1/action-center/notifications',{cache:'no-store'});if(notices.ok&&active){const rows=await notices.json();setUnread(rows.filter((n:{state:string})=>n.state==='unread').length);}}catch{}
    }
   }catch(e){if(active)setError((e as Error).message);}finally{inFlight=false;}
  }
  check();const timer=window.setInterval(check,15000);
  window.addEventListener('focus',check);document.addEventListener('visibilitychange',check);
  return()=>{active=false;clearInterval(timer);window.removeEventListener('focus',check);document.removeEventListener('visibilitychange',check);};
 },[identity.id]);
 async function changePassword(e:React.FormEvent<HTMLFormElement>){
  e.preventDefault();const form=e.currentTarget;const fields=new FormData(form);setBusy(true);setError('');setNotice('');
  try{
   const body={current_password:fields.get('current_password'),new_password:fields.get('new_password'),confirm_password:fields.get('confirm_password')};
   if(body.new_password!==body.confirm_password)throw new Error('New passwords do not match.');
   const r=await fetch('/api/v1/auth/password',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)});
   const result=await r.json();if(!r.ok)throw new Error(typeof result.detail==='string'?result.detail:'Unable to change password.');
   current.current=result.profile;setProfile(result.profile);onCsrfChanged(result.csrf_token);form.reset();setChanging(false);setNotice('Password changed. Other sessions have been signed out.');
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}
 }
 async function signOut(all=false){setBusy(true);setError('');try{
  const r=await fetch('/api/v1/auth/'+(all?'logout-all':'logout'),{method:'POST',headers:{'X-CSRF-Token':csrf}});
  if(!r.ok)throw new Error('Unable to sign out. Refresh and try again.');location.reload();
 }catch(e){setError((e as Error).message);setBusy(false);}}
 async function copy(){try{await navigator.clipboard.writeText(profile?.upn||identity.username);setNotice('UPN copied.');}catch{setError('Select the UPN above and copy it.');}}
 return <details className="profile-menu" ref={details} onToggle={()=>{if(!details.current?.open){setChanging(false);setNotice('');}}}>
  <summary aria-label={'Account: '+(profile?.upn||identity.username)}><span className="profile-avatar" aria-hidden="true">{(profile?.display_name||identity.username).slice(0,2).toUpperCase()}</span><span><strong>{profile?.display_name||'Signed-in account'}</strong><span className="profile-upn">{profile?.upn||identity.username}</span><small>{profile?'Employee ID: '+profile.employee_id:'Verifying profile…'}</small>{unread>0&&<small className="profile-unread">{unread} unread Action Center notification{unread===1?'':'s'}</small>}</span><span aria-hidden="true">▾</span></summary>
  <section className="profile-panel" aria-label="Your profile"><h2>Your profile</h2>{profile&&<><dl><dt>UPN / sign-in</dt><dd>{profile.upn}</dd><dt>Employee ID</dt><dd>{profile.employee_id} <small>Managed by an administrator</small></dd><dt>Organization</dt><dd>{employers[profile.organization]||profile.organization}</dd><dt>Roles</dt><dd>{profile.roles.map(r=>r.split('_').join(' ')).join(', ')}</dd><dt>Active clean-team scopes</dt><dd>{profile.clean_team_scopes.length?<ul>{profile.clean_team_scopes.map(s=><li key={s.matter+s.scope}>{s.matter} · {s.scope}</li>)}</ul>:'None currently permitted'}</dd><dt>Session expires</dt><dd>{new Date(profile.expires_at*1000).toLocaleString()}</dd></dl><p className="muted">Scopes describe membership; access to each document still requires a policy check.</p></>}
   {error&&<p className="error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
   {profile?.organization==='firm'&&profile.roles.some(r=>['firm_lawyer','legal_sme','antitrust_counsel'].includes(r))&&<p><a href="/portal?view=Action%20Center">Open Action Center · {unread} unread</a></p>}
   <div className="profile-actions"><button type="button" onClick={copy}>Copy UPN</button><button type="button" disabled={!profile||busy} onClick={()=>{setChanging(!changing);setNotice('');setError('');}}>Change password</button></div>
   {changing&&<form onSubmit={changePassword} className="profile-password"><label>Current password<input name="current_password" type="password" autoComplete="current-password" required maxLength={256}/></label><label>New password<input name="new_password" type="password" autoComplete="new-password" required minLength={15} maxLength={256}/></label><label>Confirm new password<input name="confirm_password" type="password" autoComplete="new-password" required minLength={15} maxLength={256}/></label><small>Use 15–256 characters. Your current session stays signed in; other sessions are revoked.</small><div className="profile-actions"><button className="primary" disabled={busy}>Save password</button><button type="button" onClick={()=>setChanging(false)} disabled={busy}>Cancel</button></div></form>}
   <div className="profile-actions"><button type="button" disabled={busy} onClick={()=>signOut()}>Sign out</button><button type="button" disabled={busy} onClick={()=>signOut(true)}>Sign out all sessions</button></div><small>Tabs on the same portal share a sign-in cookie. To test a second account independently, use a separate browser profile.</small>
  </section>
 </details>;
}
