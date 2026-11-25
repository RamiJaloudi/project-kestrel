import {useEffect,useRef,useState} from 'react';
type Session={id:string;sequence:number;active:boolean;active_seconds:number;idle_seconds:number;unobserved_seconds:number;idle_timeout_seconds:number;notice:string};
export default function ReaderTiming({taskId,csrf,root}:{taskId:string;csrf:string;root:React.RefObject<HTMLDialogElement>}){
 const [session,setSession]=useState<Session|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[status,setStatus]=useState('Timing is off. Enable it explicitly while reviewing this source.');
 const live=useRef<Session|null>(null),gesture=useRef(false),sending=useRef(false),mounted=useRef(true),enabled=useRef(false);
 async function request(path:string,body?:unknown){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);try{const r=await fetch('/api/v1'+path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},body:body?JSON.stringify(body):undefined});const v=await r.json();if(!r.ok)throw new Error(v.detail||'Timing request denied');return v;}finally{clearTimeout(timer);}}
 async function stop(reason='Timing stopped. Unsampled intervals remain unmeasured.'){
  enabled.current=false;const s=live.current;if(!s)return;live.current=null;
  try{const current:Session=await request('/review-clocks/sessions/'+s.id);if(current.active)await request('/review-clocks/sessions/'+s.id+'/receipts',{operation:'close',expected_sequence:current.sequence,interaction:false,request_key:crypto.randomUUID()});}
  catch{reason='Timing stopped locally. The server lease will expire within 90 seconds; gaps receive no active credit.';}
  if(mounted.current){setSession(null);setStatus(reason);}
 }
 async function begin(){setBusy(true);setError('');try{
  if(document.visibilityState!=='visible'||!document.hasFocus())throw new Error('Bring this reader into focus before enabling timing.');
  const t=await request('/review-work/tasks/'+taskId);const s:Session=await request('/review-clocks/tasks/'+taskId+'/sessions',{expected_revision:t.revision,request_key:crypto.randomUUID()});
  live.current=s;enabled.current=true;gesture.current=false;setSession(s);setStatus('Interaction estimates enabled. Quiet reading may remain unobserved.');
 }catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 useEffect(()=>{mounted.current=true;
  const activity=(e:Event)=>{if(e.isTrusted&&enabled.current)gesture.current=true;};
  const hide=()=>{if(document.visibilityState!=='visible')void stop('Timing stopped because the reader became hidden. Enable it again when you return.');};
  const blur=()=>{if(enabled.current)void stop('Timing stopped when this window lost focus.');};
  const element=root.current;for(const event of ['pointerdown','keydown','wheel'])element?.addEventListener(event,activity,{passive:true});
  document.addEventListener('visibilitychange',hide);window.addEventListener('blur',blur);
  const timer=setInterval(async()=>{
   const s=live.current;if(!enabled.current||!s||sending.current)return;
   if(document.visibilityState!=='visible'||!document.hasFocus()){void stop();return;}
   sending.current=true;const interaction=gesture.current;gesture.current=false;
   try{const v:Session=await request('/review-clocks/sessions/'+s.id+'/receipts',{operation:'sample',expected_sequence:s.sequence,interaction,request_key:crypto.randomUUID()});if(live.current?.id===s.id){live.current=v;if(mounted.current)setSession(v);}}
   catch(e){enabled.current=false;if(mounted.current)setError('Timing paused after a denied or uncertain observation. '+(e as Error).message);void stop();}
   finally{sending.current=false;}
  },15000);
  return()=>{mounted.current=false;clearInterval(timer);for(const event of ['pointerdown','keydown','wheel'])element?.removeEventListener(event,activity);document.removeEventListener('visibilitychange',hide);window.removeEventListener('blur',blur);void stop();};
 },[taskId,csrf]);
 return <div className="reader-timing"><strong>Review timing</strong><span role="status">{status}</span>{session&&<span>Interaction estimate {session.active_seconds}s · idle {session.idle_seconds}s · unobserved {session.unobserved_seconds}s · idle threshold {session.idle_timeout_seconds/60} min</span>}<button disabled={busy} onClick={()=>session?void stop():void begin()}>{session?'Stop timing':'Enable interaction timing'}</button>{error&&<span className="error" role="alert">{error}</span>}<small>Estimates are not verified work or billable time. An open tab alone earns no active credit.</small></div>;
}
