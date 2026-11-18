from datetime import date
from sqlalchemy import select
from fastapi import HTTPException
from .models import Hive,Visit,CareAction
from .season_models import ApiaryMove
from .yard_service import require,audit,latest

def eligibility(db,h):
    active=db.scalar(select(CareAction.id).join(Visit,CareAction.visit_id==Visit.id).where(Visit.hive_id==h.id,CareAction.status.in_(['planned','executed','rechecked'])))
    if h.care_state!='winter_ready' or active or not h.queen_present or h.colony_frames<5:raise HTTPException(409,'须越冬合格、有王且至少5框，无活跃处置才能转场')

def request_move(db,b,u):
    h=require(db,Hive,b.hive_id,True);eligibility(db,h)
    if b.destination.strip()==h.site or len(b.health_note.strip())<5:raise HTTPException(409,'目的地不得与原址相同，检疫说明须完整')
    if db.scalar(select(ApiaryMove.id).where(ApiaryMove.hive_id==h.id,ApiaryMove.state.in_(['requested','approved']))):raise HTTPException(409,'该箱已有在途转场')
    v=db.get(Visit,latest(db,h.id))
    row=ApiaryMove(**b.model_dump(),origin_snapshot={'site':h.site,'hive_code':h.code,'queen_present':h.queen_present,'frames':h.colony_frames,'latest_visit_id':v.id if v else None,'weight_kg':v.weight_kg if v else None})
    db.add(row);audit(db,u,f'申请转场 {h.code} {h.site}→{b.destination}');db.commit();return row

def transition(db,key,u,action):
    ref=require(db,ApiaryMove,key);h=require(db,Hive,ref.hive_id,True);row=require(db,ApiaryMove,key,True)
    if action=='cancel':
        if row.state not in ['requested','approved']:raise HTTPException(409,'转场已完成或已取消')
        row.state='cancelled'
    elif action=='approve':
        if row.state!='requested':raise HTTPException(409,'仅待检疫申请可签发')
        eligibility(db,h)
        if h.site!=row.origin_snapshot['site']:raise HTTPException(409,'原址已变化，请撤销重新申请')
        row.state='approved';row.approved_by=u.email
    else:
        if row.state!='approved':raise HTTPException(409,'须先主管检疫签发，实际转场不得重复')
        eligibility(db,h)
        if row.move_date>date.today():raise HTTPException(409,'尚未到计划转场日')
        if h.site!=row.origin_snapshot['site']:raise HTTPException(409,'原址已变化，禁止覆盖')
        h.site=row.destination;row.state='moved';row.moved_by=u.email
    audit(db,u,f'转场{key} {action}');db.commit();return row
