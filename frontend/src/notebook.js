import {api} from './api.js';
export const book={hives:[],visits:[],care:[],lots:[],issues:[],queens:[],moves:[],insulationLots:[],installs:[],spring:[],selectedHive:31,selectedVisit:null,selectedCare:null,planning:false,showAll:false};
export async function openNotebook(){[book.hives,book.visits,book.care,book.lots,book.issues,book.queens,book.moves,book.insulationLots,book.installs,book.spring]=await Promise.all([api('/hives'),api('/visits'),api('/care'),api('/feed-lots'),api('/feed-issues'),api('/queen-observations'),api('/moves'),api('/insulation-lots'),api('/insulation-installs'),api('/spring-reviews')]);}
export function latestVisits(){const found=new Map();for(const visit of book.visits)if(!found.has(visit.hive_id))found.set(visit.hive_id,visit);return [...found.values()];}
