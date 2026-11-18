from datetime import date
from sqlalchemy import select
from fastapi import HTTPException
from .models import CareAction,Hive,Visit
from .resource_models import FeedLot,FeedIssue
from .yard_service import require,audit

def receive(db,body,user):
    if body.expires_on<date.today():raise HTTPException(409,'新到货饲料不能已过期')
    if db.scalar(select(FeedLot).where(FeedLot.code==body.code)):raise HTTPException(409,'饲料批号已存在')
    lot=FeedLot(**body.model_dump(),available_kg=body.received_kg);db.add(lot)
    audit(db,user,f'饲料入库 {body.code} {body.received_kg}kg');db.commit();return lot

def state(db,key,body,user):
    lot=require(db,FeedLot,key,True)
    if lot.state==body.state:raise HTTPException(409,'批次已处于该状态')
    lot.state=body.state;audit(db,user,f'饲料批次 {lot.code} 状态{body.state}');db.commit();return lot

def issue(db,body,user):
    care=require(db,CareAction,body.care_id,True)
    if care.kind!='feed' or care.status!='planned':raise HTTPException(409,'仅计划中的饲喂处置可以领料')
    if db.scalar(select(FeedIssue).where(FeedIssue.care_id==care.id)):raise HTTPException(409,'该饲喂已领料，禁止重复扣料')
    lot=require(db,FeedLot,body.lot_id,True)
    if lot.state!='active':raise HTTPException(409,'隔离批次禁止领用')
    if lot.expires_on<date.today():raise HTTPException(409,'饲料已过期，禁止领用')
    if lot.available_kg<care.feed_kg:raise HTTPException(409,'饲料可用库存不足计划用量')
    lot.available_kg=round(lot.available_kg-care.feed_kg,4)
    item=FeedIssue(care_id=care.id,lot_id=lot.id,kg=care.feed_kg,issued_by=user.email);db.add(item)
    audit(db,user,f'饲料领用 {lot.code} 处置{care.id} {care.feed_kg}kg 余{lot.available_kg}kg');db.commit();return item

def execution_guard(db,care):
    item=db.scalar(select(FeedIssue).where(FeedIssue.care_id==care.id).with_for_update())
    if not item or item.state!='issued':raise HTTPException(409,'饲喂执行前须按计划完成批次领料')
    lot=require(db,FeedLot,item.lot_id,True)
    if lot.state!='active' or lot.expires_on<date.today():raise HTTPException(409,'已领批次隔离或过期，不可执行饲喂，请取消退料')
    item.state='used'

def cancel(db,key,body,user):
    care=require(db,CareAction,key,True)
    if care.status!='planned':raise HTTPException(409,'仅未执行计划可以取消退料')
    item=db.scalar(select(FeedIssue).where(FeedIssue.care_id==key).with_for_update())
    if item:
        if item.state!='issued':raise HTTPException(409,'领料已执行或已退，不得重复退料')
        lot=require(db,FeedLot,item.lot_id,True);lot.available_kg=round(lot.available_kg+item.kg,4)
        item.state='returned';item.returned_by=user.email;item.return_reason=body.reason
    care.status='cancelled'
    visit=require(db,Visit,care.visit_id,True);hive=require(db,Hive,visit.hive_id,True)
    visit.status='screened';hive.care_state='observe' if visit.queen_seen else 'needs_care'
    audit(db,user,f'取消处置 {key}，未执行饲料退回原批，依据{body.reason}');db.commit();return care
