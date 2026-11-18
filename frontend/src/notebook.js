import {api} from './api.js';
export const book={hives:[],visits:[],care:[],lots:[],issues:[],queens:[],moves:[],insulationLots:[],installs:[],spring:[],seasons:[],seasonId:null,season:null,selectedHive:31,selectedVisit:null,selectedCare:null,planning:false,showAll:false};
export const activeSeason=()=>book.seasons.find(s=>s.state==='active');
export const seasonReadOnly=()=>!!book.season&&book.season.state!=='active';
export async function openNotebook(){
  book.seasons=await api('/seasons');
  if(book.seasonId==null||!book.seasons.some(s=>s.id===book.seasonId))book.seasonId=(activeSeason()||book.seasons[0])?.id??null;
  book.season=book.seasons.find(s=>s.id===book.seasonId)||null;
  const scope=book.seasonId!=null?'?season_id='+book.seasonId:'';
  const [hives,visits,care,lots,issues,queens,moves,insulationLots,installs,spring]=await Promise.all([api('/hives'),api('/visits'+scope),api('/care'+scope),api('/feed-lots'),api('/feed-issues'),api('/queen-observations'),api('/moves'+scope),api('/insulation-lots'),api('/insulation-installs'+scope),api('/spring-reviews'+scope)]);
  const careIds=new Set(care.map(c=>c.id));
  book.hives=hives;book.visits=visits;book.care=care;book.lots=lots;book.moves=moves;book.insulationLots=insulationLots;book.installs=installs;book.spring=spring;
  book.issues=issues.filter(i=>careIds.has(i.care_id));book.queens=queens.filter(q=>careIds.has(q.care_id));
}
export const readOnlyNotice=(what='巡检与处置')=>seasonReadOnly()?`<div class="readonly">当前查看的是已封存越冬季，${what}只能查阅，不能新增、复查或关闭。请切换回进行中的越冬季办理。</div>`:'';
export function latestVisits(){const found=new Map();for(const visit of book.visits)if(!found.has(visit.hive_id))found.set(visit.hive_id,visit);return [...found.values()];}
