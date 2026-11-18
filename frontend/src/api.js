export const account=()=>JSON.parse(localStorage.getItem('apiary-account')||'null');
export const loginAs=x=>localStorage.setItem('apiary-account',JSON.stringify(x));
export async function api(path,method='GET',body){const response=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json',...(account()?{Authorization:'Bearer '+account().token}:{})},body:body?JSON.stringify(body):undefined});const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;}
