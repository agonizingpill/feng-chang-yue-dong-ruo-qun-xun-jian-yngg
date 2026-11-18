import {book,openNotebook} from '../notebook.js';import {api,account} from '../api.js';import {headline} from '../components/notes.js';import {text,fields,toast,when} from '../utils.js';

const newLabel=()=>{const match=/\b(\d{4})\b/.exec(book.season?.code||'');const y=(match?Number(match[1]):new Date().getFullYear())+1;return `${y}—${y+1} 越冬季`;};
const requestKey=()=>'apiary-rollover-request:'+(book.season?.id??'none');
// Reuse one request id until the receipt is confirmed, so a lost response is
// retried idempotently instead of opening a second season.
const requestId=()=>{const key=requestKey();let id=localStorage.getItem(key);if(!id){id=`${account().email.split('@')[0]}-${Date.now()}-${Math.random().toString(36).slice(2,10)}`;localStorage.setItem(key,id);}return id;};

export function render(){
  const admin=account().role==='admin',season=book.season,canClose=season&&season.state==='active';
  return headline('10 / SEASON ROLLOVER','把这一季收好，再打开下一季','结季前逐项核对：没有尚在进行的处置、没有未到站的转场、没有还没结束的筛查，主管才能封存旧季并从“待巡检”开始新季。')+`<div class="resource-layout"><aside><section class="sheet"><h2>当前查看的越冬季</h2>${season?`<span class="code">${text(season.code)}</span><p><strong>${text(season.label)}</strong><br>${season.state==='active'?'进行中，可登记巡检与处置':'已封存，全部记录只读'}</p><p class="hint">巡检 ${season.visits} 条 · 处置 ${season.care_actions} 条<br>转场 ${season.moves} 条 · 保温 ${season.insulation_installs} 次<br>春检 ${season.spring_reviews} 条</p>`:'<p class="hint">还没有越冬季记录。</p>'}<p class="hint">新季沿用蜂箱与实物库存（饲料批次、保温物料）；旧季分值、春检资格与处置状态不沿用，筛查算法不变。</p></section>${canClose?`<section class="sheet"><h2>主管结季并开新季</h2><form id="close-form"><label>新季名称<input name="label" value="${text(newLabel())}" minlength="3" required></label><div class="rule">结季会封存旧季全部记录，蜂箱回到“待巡检”，旧季入口随即只读。</div><button class="primary" ${admin?'':'disabled'}>主管结季并开新季</button></form><div id="blocker-lines" class="hint"></div></section>`:`<section class="sheet"><h2>旧季已封存</h2><p class="hint">旧季巡检与处置只能查看，不能新增、复查或关闭。请到进行中的越冬季办理。</p></section>`}</aside><section><h2>越冬季档案</h2>${book.seasons.map(s=>`<article class="sheet"><span class="code">${text(s.code)}</span> <span class="badge ${s.state==='active'?'screened':'stale'}">${s.state==='active'?'进行中':'已封存'}</span><h3>${text(s.label)} ${s.id===book.seasonId?'<span class="badge closed">正在查看</span>':''}</h3><p class="hint">开季 ${text(s.opened_by||'—')} · ${when(s.opened_at)}<br>${s.state==='closed'?'封存 '+text(s.closed_by||'—')+' · '+when(s.closed_at):'巡检 '+s.visits+' 条 / 处置 '+s.care_actions+' 条'}</p><div class="actions"><button data-view="${s.id}">${s.id===book.seasonId?'当前查看':'查看该季巡检与处置'}</button></div></article>`).join('')||'<div class="empty">尚未建立越冬季档案</div>'}</section></div>`;
}

export function bind(render){
  document.querySelectorAll('[data-view]').forEach(b=>b.onclick=async()=>{book.seasonId=Number(b.dataset.view);book.planning=false;book.selectedCare=null;book.selectedVisit=null;await openNotebook();render();});
  const form=document.querySelector('#close-form');if(!form)return;
  const preview=async()=>{try{const r=await api('/seasons/rollover/preview');const el=document.querySelector('#blocker-lines');if(!el)return;el.innerHTML=r.can_close?'可以结季：没有未完成的处置、转场与筛查。':`<div class="rule">暂不能结季，请先处理以下 ${r.blockers.length} 项：</div><ul>${r.blockers.map(b=>`<li>${text(b.message)}</li>`).join('')}</ul>`;const button=form.querySelector('button');if(button)button.disabled=!r.can_close||account().role!=='admin';}catch(e){}};
  preview();
  form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button');button.disabled=true;try{const opened=await api('/seasons/rollover','POST',{request_id:requestId(),label:fields(e.target).label});localStorage.removeItem(requestKey());book.seasonId=opened.id;book.planning=false;book.selectedCare=null;book.selectedVisit=null;await openNotebook();location.hash='yard';render();toast(`已封存旧季，${opened.label} 从待巡检开始`);}catch(err){button.disabled=false;toast(err.message);preview();}};
}
