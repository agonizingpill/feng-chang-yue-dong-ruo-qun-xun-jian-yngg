from datetime import datetime
from sqlalchemy import select
from fastapi import HTTPException
from .models import Hive,Visit,CareAction
from .yard_service import require,audit,latest

def plan(db,body,user):
    visit=require(db,Visit,body.visit_id,True);hive=require(db,Hive,visit.hive_id,True)
    if latest(db,hive.id)!=visit.id:raise HTTPException(409,'请基于该箱最新巡检建立处置')
    if visit.status not in ['screened','needs_requeen']:raise HTTPException(409,'须先完成弱群筛查，或为无王复查建立换王处置')
    if body.feed_kg>3:raise HTTPException(409,'每箱单次饲喂不得超过3kg，请拆分到后续复查计划')
    if body.kind=='feed' and body.feed_kg<=0:raise HTTPException(409,'饲喂量必须大于0')
    if body.kind=='requeen' and body.feed_kg!=0:raise HTTPException(409,'换王计划饲喂量应为0，饲喂需单独记录')
    if visit.status=='needs_requeen' and body.kind!='requeen':raise HTTPException(409,'无王群复查失败后必须建立换王处置')
    active=db.scalar(select(CareAction).where(CareAction.visit_id==visit.id,CareAction.status.in_(['planned','executed','rechecked'])))
    if active:raise HTTPException(409,'该次巡检已有未完成处置')
    action=CareAction(**body.model_dump(),status='planned');visit.status='caring';hive.care_state='caring'
    db.add(action);audit(db,user,f'建立{body.kind}处置 {hive.code} 饲喂{body.feed_kg}kg');db.commit();return action

def execute(db,key,body,user):
    action=require(db,CareAction,key,True)
    if action.status!='planned':raise HTTPException(409,'仅计划中的处置可以登记执行')
    visit=require(db,Visit,action.visit_id,True);hive=require(db,Hive,visit.hive_id,True)
    if action.kind=='feed':
        from .feed_service import execution_guard
        execution_guard(db,action)
    if action.kind=='requeen':
        if not body.queen_installed:raise HTTPException(409,'换王必须确认新蜂王已实际入箱')
        action.queen_installed=True;hive.queen_present=True
    action.status='executed';action.executed_at=datetime.utcnow()
    audit(db,user,f'处置 {key} 已执行，{action.kind}，换王确认{action.queen_installed}');db.commit();return action

def followup(db,key,body,user):
    action=require(db,CareAction,key,True)
    if action.status not in ['executed','rechecked']:raise HTTPException(409,'请先执行处置，已关闭或已转换王记录不可覆盖复查')
    visit=require(db,Visit,action.visit_id,True);hive=require(db,Hive,visit.hive_id,True)
    action.followup_weight=body.followup_weight;action.followup_queen=body.followup_queen;action.followup_frames=body.followup_frames
    hive.queen_present=body.followup_queen;hive.colony_frames=body.followup_frames
    if action.kind=='feed' and (not visit.queen_seen or not body.followup_queen):
        action.status='needs_requeen';visit.status='needs_requeen';hive.care_state='needs_requeen'
    else:action.status='rechecked';visit.status='followup'
    audit(db,user,f'处置 {key} 复查 {body.followup_weight}kg，见王{body.followup_queen}');db.commit();return action

def close(db,key,user):
    action=require(db,CareAction,key,True);visit=require(db,Visit,action.visit_id,True);hive=require(db,Hive,visit.hive_id,True)
    if action.kind=='feed' and (not visit.queen_seen or action.followup_queen is False):raise HTTPException(409,'无王群不能仅用饲喂关闭，请建立换王处置')
    if action.status!='rechecked' or action.followup_weight is None:raise HTTPException(409,'缺少执行后复查记录，不能关闭')
    if not action.followup_queen or not hive.queen_present:raise HTTPException(409,'换王后仍未见王，须重新复查，不能关闭')
    if action.kind=='requeen' and not action.queen_installed:raise HTTPException(409,'没有换王执行依据')
    if action.kind=='requeen':
        from .queen_service import closure_guard
        closure_guard(db,action)
    if action.followup_frames is None or action.followup_frames<5:raise HTTPException(409,'复查蜂量不足5框，请继续保群，不能关闭越冬处置')
    if action.followup_weight<visit.weight_kg:raise HTTPException(409,'复查体重仍低于巡检，请继续排查越冬风险')
    action.status='closed';action.closed_at=datetime.utcnow();visit.status='closed';hive.care_state='winter_ready'
    for old in db.scalars(select(Visit).where(Visit.hive_id==hive.id,Visit.id!=visit.id,Visit.status.in_(['recorded','screened','blocked']))).all():old.status='stale'
    audit(db,user,f'关闭处置 {key}，{hive.code}越冬复查通过');db.commit();return action
