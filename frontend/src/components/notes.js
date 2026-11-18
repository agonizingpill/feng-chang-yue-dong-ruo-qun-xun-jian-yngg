import {book} from '../notebook.js';import {text,num} from '../utils.js';import {CARE_STATES,VISIT_STATES} from '../constants.js';
export const headline=(n,title,description)=>`<section class="headline"><div><div class="chapter">SHANJING FIELD NOTES / ${n}</div><h1>${title}</h1><p>${description}</p></div><div class="margin-note">山荆蜂业 · 越冬手记<br>2026 / 11 / 17<br>东坡与林缘 · 9名蜂师</div></section>`;
export const badge=(state,type='visit')=>`<span class="badge ${text(state)}">${text((type==='care'?CARE_STATES:VISIT_STATES)[state]||state)}</span>`;
export const hiveName=id=>book.hives.find(h=>h.id===id)?.code||'未知蜂箱';
export const hiveOptions=()=>book.hives.map(h=>`<option value="${h.id}">${text(h.code)} · ${text(h.site)}</option>`).join('');
export function visitEvidence(v){return `<div class="ruled"><span class="code">${text(v.code)} / ${text(hiveName(v.hive_id))}</span><p class="hint">巡检体重 ${num(v.weight_kg)} kg · 箱温 ${num(v.temperature,1)}°C<br>活动 ${num(v.activity,0)} 只/分钟 · 余饲 ${num(v.feed_left)} kg<br>${v.queen_seen?'巡检见王':'巡检未见王'} · 蜂量 ${v.colony_frames} 框</p></div>`;}
export function scoreEvidence(v){return `<p class="hint">异常分值 ${num(v.anomaly_score,4)} / 阈值 ${num(v.model_evidence?.threshold,4)}<br>${v.anomaly_flag?'偏离参考分布，建议核查原因':'未低于异常阈值，仍需结合王况判断'}</p>`;}
