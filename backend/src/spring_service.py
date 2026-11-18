from sqlalchemy import select,func
from fastapi import HTTPException
from .models import Hive,Visit,CareAction
from .season_models import InsulationInstall,SpringReview
from .yard_service import require,audit,latest

def record(db,b,u):
    h=require(db,Hive,b.hive_id,True)
    if h.care_state!='winter_ready':raise HTTPException(409,'须已越冬合格的蜂群才能春检')
    if db.scalar(select(SpringReview.id).where(SpringReview.hive_id==h.id)):raise HTTPException(409,'该箱已有本季春检')
    install=db.scalar(select(InsulationInstall).where(InsulationInstall.hive_id==h.id,InsulationInstall.state=='accepted'))
    if not install:raise HTTPException(409,'须有主管验收的保温安装')
    v=db.get(Visit,latest(db,h.id));care=db.scalar(select(CareAction).join(Visit,CareAction.visit_id==Visit.id).where(Visit.hive_id==h.id,CareAction.status=='closed').order_by(CareAction.id.desc()))
    baseline_weight=care.followup_weight if care else v.weight_kg if v else None
    rescue=not b.queen_seen or b.frames<5 or b.mortality_pct>20
    row=SpringReview(**b.model_dump(),install_id=install.id,state='rescue' if rescue else 'pending',rescue_after_care_id=db.scalar(select(func.coalesce(func.max(CareAction.id),0))),winter_snapshot={'site':h.site,'hive_code':h.code,'care_state':h.care_state,'queen_present':h.queen_present,'frames':h.colony_frames,'weight_kg':baseline_weight,'closed_care_id':care.id if care else None,'latest_visit_id':v.id if v else None,'insulation_id':install.id,'opening_weight_delta':round(b.opening_weight-baseline_weight,3) if baseline_weight else None})
    h.queen_present=b.queen_seen;h.colony_frames=b.frames
    if rescue:h.care_state='spring_rescue'
    db.add(row);audit(db,u,f'春检 {h.code} 死亡率{b.mortality_pct}% {row.state}');db.commit();return row

def pass_review(db,key,b,u):
    ref=require(db,SpringReview,key);h=require(db,Hive,ref.hive_id,True);row=require(db,SpringReview,key,True)
    if row.state not in ['pending','rescue']:raise HTTPException(409,'春检已通过，不能重复审签')
    if len(b.resolution.strip())<5:raise HTTPException(409,'须填写复苏审查依据')
    if row.state=='rescue':
        if not b.rescue_care_id:raise HTTPException(409,'救护春检须关联春检后新建且已关闭的处置')
        care=require(db,CareAction,b.rescue_care_id);visit=require(db,Visit,care.visit_id)
        if visit.hive_id!=h.id or care.id<=row.rescue_after_care_id or care.status!='closed' or not care.closed_at or care.closed_at<row.created_at:raise HTTPException(409,'必须同箱、春检后新建且闭环的救护处置')
        if not care.followup_queen or not care.followup_frames or care.followup_frames<5:raise HTTPException(409,'救护复查仍不满足有王和5框')
        row.rescue_care_id=care.id
    elif b.rescue_care_id:raise HTTPException(409,'正常春检不绑定无关救护处置')
    active=db.scalar(select(CareAction.id).join(Visit,CareAction.visit_id==Visit.id).where(Visit.hive_id==h.id,CareAction.status.in_(['planned','executed','rechecked'])))
    if active or not h.queen_present or h.colony_frames<5:raise HTTPException(409,'蜂群仍有活跃处置或未恢复有王5框')
    row.resolution=b.resolution.strip();row.passed_by=u.email;row.state='passed';h.care_state='spring_ready';audit(db,u,f'春检{key}复苏通过');db.commit();return row
