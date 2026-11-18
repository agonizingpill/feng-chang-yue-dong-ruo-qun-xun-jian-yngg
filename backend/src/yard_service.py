import uuid,json
from sqlalchemy import select,func
from fastapi import HTTPException
from .models import Hive,Visit,CareAction,Audit

def require(db,model,key,lock=False):
    q=select(model).where(model.id==key)
    if lock:q=q.with_for_update().execution_options(populate_existing=True)
    row=db.scalar(q)
    if not row:raise HTTPException(404,'蜂场记录不存在')
    return row

def audit(db,user,text):db.add(Audit(actor=user.email,action=text))
def latest(db,hive_id):return db.scalar(select(func.max(Visit.id)).where(Visit.hive_id==hive_id))

def save_hive(db,body,user,key=None):
    hive=require(db,Hive,key,True) if key else Hive()
    if key:
        from .season_models import ApiaryMove
        if db.scalar(select(ApiaryMove.id).where(ApiaryMove.hive_id==hive.id,ApiaryMove.state.in_(['requested','approved']))):raise HTTPException(409,'在途转场期间蜂箱档案冻结，可先撤销申请')
    if key and hive.care_state in ['caring','needs_requeen']:raise HTTPException(409,'该蜂群有进行中的处置，王况和框数请在复查簿记录')
    other=db.scalar(select(Hive).where(Hive.code==body.code,Hive.id!=key)) if key else db.scalar(select(Hive).where(Hive.code==body.code))
    if other:raise HTTPException(409,'蜂箱编号已存在')
    for k,v in body.model_dump().items():setattr(hive,k,v)
    db.add(hive);audit(db,user,f'维护蜂箱 {body.code}');db.commit();return hive

def record_visit(db,body,user):
    hive=require(db,Hive,body.hive_id,True)
    if hive.care_state in ['caring','needs_requeen']:raise HTTPException(409,'该箱处置未结束，请在处置簿登记复查，不能覆盖原巡检')
    if db.scalar(select(Visit).where(Visit.code==body.code)):raise HTTPException(409,'巡检编号已存在')
    visit=Visit(**body.model_dump());hive.queen_present=body.queen_seen;hive.colony_frames=body.colony_frames;hive.care_state='observe' if body.queen_seen else 'needs_care'
    db.add(visit);audit(db,user,f'巡箱 {hive.code} / {body.code} {body.weight_kg}kg');db.commit();return visit

def enqueue_screen(db,user,queue,key=None):
    if key:
        v=require(db,Visit,key,True)
        if latest(db,v.hive_id)!=v.id:raise HTTPException(409,'该箱已有更新巡检，请筛查最新记录')
        candidates=[v]
    else:
        ids=select(func.max(Visit.id)).group_by(Visit.hive_id)
        candidates=db.scalars(select(Visit).where(Visit.id.in_(ids),Visit.status.in_(['recorded','screened','blocked'])).order_by(Visit.id).with_for_update()).all()
    if not candidates:raise HTTPException(409,'没有可筛查的最新巡检，请先登记读数')
    for v in candidates:
        if v.status not in ['recorded','screened','blocked']:raise HTTPException(409,'已进入处置的巡检不能重新筛查或覆盖原值')
        v.status='screening'
    jobid=uuid.uuid4().hex;ids=[v.id for v in candidates]
    audit(db,user,f'弱群筛查 {len(ids)} 箱最新巡检');db.commit()
    queue.set('apiary:screen:'+jobid,json.dumps({'status':'queued'}),ex=86400);queue.rpush('apiary:screening',json.dumps({'job_id':jobid,'visit_ids':ids}));return {'job_id':jobid,'count':len(ids)}
