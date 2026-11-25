import {useEffect,useState} from 'react';

type MatterChoice={id:string;client_number?:string};
// URLs carry selection only. The API still supplies and authorizes every choice.
export function selectPermittedMatter(rows:MatterChoice[]):string{
 const requested=new URLSearchParams(location.search).get('matter');
 if(requested)return rows.some(row=>row.id===requested)?requested:'';
 return rows.find(row=>row.client_number==='012345')?.id||rows[0]?.id||'';
}
export function useMatterSelection(){
 const [matter,setMatter]=useState('');
 useEffect(()=>{
  if(!matter)return;
  const url=new URL(location.href),previous=url.searchParams.get('matter');
  if(previous&&previous!==matter){for(const key of ['source','finding','revision_id','unit','start','end','historical','report','release','section'])url.searchParams.delete(key);}
  url.searchParams.set('matter',matter);history.replaceState(null,'',url);
 },[matter]);
 return [matter,setMatter] as const;
}
