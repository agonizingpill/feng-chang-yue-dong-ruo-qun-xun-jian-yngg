from datetime import date
from sqlalchemy import select
from fastapi import HTTPException
from .models import CareAction
from .resource_models import QueenObservation
from .yard_service import require,audit

def observe(db,body,user,key=None):
    care=require(db,CareAction,body.care_id,True)
    if care.kind!='requeen' or care.status not in ['executed','rechecked'] or not care.queen_installed:raise HTTPException(409,'须先实际执行换王，已关闭或未执行处置不可登记观察')
    if body.installed_on>date.today() or not care.executed_at or body.installed_on!=care.executed_at.date():raise HTTPException(409,'引入日期须与换王执行日期一致，不能填未来日期')
    item=require(db,QueenObservation,key,True) if key else None
    if item and (item.care_id!=care.id or item.state!='observing'):raise HTTPException(409,'主管已确认的蜂王观察不可改写或换关联')
    if not key and db.scalar(select(QueenObservation).where(QueenObservation.care_id==care.id)):raise HTTPException(409,'该换王处置已有观察记录，请更新原记录')
    other=db.scalar(select(QueenObservation).where(QueenObservation.queen_code==body.queen_code,QueenObservation.id!=key)) if key else db.scalar(select(QueenObservation).where(QueenObservation.queen_code==body.queen_code))
    if other:raise HTTPException(409,'蜂王编号已用于其他处置')
    if not item:item=QueenObservation()
    for k,v in body.model_dump().items():setattr(item,k,v)
    item.state='observing';db.add(item);audit(db,user,f'蜂王引入观察 处置{care.id} {body.queen_code} 接受{body.accepted} 见卵{body.eggs_seen}');db.commit();return item

def confirm(db,key,user):
    item=require(db,QueenObservation,key);care=require(db,CareAction,item.care_id,True);item=require(db,QueenObservation,key,True)
    if item.state!='observing' or care.status not in ['executed','rechecked']:raise HTTPException(409,'已确认或处置已关闭，不能重复确认')
    if not item.accepted or not item.eggs_seen:raise HTTPException(409,'新王未被接受或未见卵，继续观察，不能确认')
    item.state='confirmed';item.confirmed_by=user.email
    audit(db,user,f'主管确认蜂王观察 {item.queen_code} 接受且已见卵');db.commit();return item

def closure_guard(db,care):
    item=db.scalar(select(QueenObservation).where(QueenObservation.care_id==care.id))
    if not item or item.state!='confirmed' or not item.accepted or not item.eggs_seen:raise HTTPException(409,'换王关闭须有新王接受、见卵及主管确认的观察依据')
