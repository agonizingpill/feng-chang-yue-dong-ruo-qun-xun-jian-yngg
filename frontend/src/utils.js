export const text=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const num=(x,n=2)=>x==null?'—':Number(x).toFixed(n);
export const fields=form=>Object.fromEntries(new FormData(form));
export const delay=ms=>new Promise(r=>setTimeout(r,ms));
export const when=x=>x?new Date(x+'Z').toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'尚未记录';
export function toast(value){const el=document.querySelector('#toast');el.textContent=value;el.classList.add('visible');clearTimeout(window.apiaryToast);window.apiaryToast=setTimeout(()=>el.classList.remove('visible'),4500);}
