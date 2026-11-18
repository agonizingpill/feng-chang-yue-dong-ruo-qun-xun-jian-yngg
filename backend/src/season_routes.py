from fastapi import APIRouter,Depends
from sqlalchemy import select,func
from .database import session
from .auth import current,editor,admin
from .models import Season,Visit,CareAction
from .yard_service import require,audit
from .season_models import ApiaryMove,InsulationLot,InsulationInstall,SpringReview
from .season_schemas import MoveInput,InsulationInput,LotState,InstallInput,VentilationInput,RemoveInput,SpringInput,PassInput,OpenSeason
from . import move_service,insulation_service,spring_service,season_service
router=APIRouter()

def _season_row(db,s):
    counts={name:db.scalar(select(func.count()).select_from(model).where(model.season_id==s.id)) or 0 for name,model in [('visits',Visit),('care_actions',CareAction),('moves',ApiaryMove),('insulation_installs',InsulationInstall),('spring_reviews',SpringReview)]}
    return {'id':s.id,'code':s.code,'label':s.label,'state':s.state,'previous_season_id':s.previous_season_id,'summary':s.summary,'opened_by':s.opened_by,'opened_at':s.opened_at,'closed_by':s.closed_by,'closed_at':s.closed_at,**counts}

@router.get('/seasons')
def seasons(u=Depends(current),db=Depends(session)):return [_season_row(db,s) for s in db.scalars(select(Season).order_by(Season.id.desc())).all()]
@router.get('/seasons/current')
def current_season(u=Depends(current),db=Depends(session)):return season_service.active_season(db)
@router.get('/seasons/rollover/preview')
def rollover_preview(u=Depends(admin),db=Depends(session)):return season_service.preview(db)
@router.post('/seasons/rollover')
def rollover(b:OpenSeason,u=Depends(admin),db=Depends(session)):return season_service.rollover(db,b,u)
@router.get('/moves')
def moves(season_id:int|None=None,u=Depends(current),db=Depends(session)):
    q=select(ApiaryMove).order_by(ApiaryMove.id.desc())
    if season_id is not None:q=q.where(ApiaryMove.season_id==season_id)
    return db.scalars(q).all()
@router.post('/moves')
def move(b:MoveInput,u=Depends(editor),db=Depends(session)):return move_service.request_move(db,b,u)
@router.post('/moves/{key}/approve')
def approve(key:int,u=Depends(admin),db=Depends(session)):return move_service.transition(db,key,u,'approve')
@router.post('/moves/{key}/complete')
def complete(key:int,u=Depends(editor),db=Depends(session)):return move_service.transition(db,key,u,'complete')
@router.post('/moves/{key}/cancel')
def cancel(key:int,u=Depends(editor),db=Depends(session)):return move_service.transition(db,key,u,'cancel')
@router.get('/insulation-lots')
def lots(u=Depends(current),db=Depends(session)):return db.scalars(select(InsulationLot).order_by(InsulationLot.id)).all()
@router.post('/insulation-lots')
def lot(b:InsulationInput,u=Depends(editor),db=Depends(session)):
    row=InsulationLot(**b.model_dump());db.add(row);audit(db,u,'登记保温物料');db.commit();return row
@router.put('/insulation-lots/{key}/state')
def state(key:int,b:LotState,u=Depends(admin),db=Depends(session)):
    row=require(db,InsulationLot,key,True);row.state=b.state;audit(db,u,'保温物料隔离状态');db.commit();return row
@router.get('/insulation-installs')
def installs(season_id:int|None=None,u=Depends(current),db=Depends(session)):
    q=select(InsulationInstall).order_by(InsulationInstall.id.desc())
    if season_id is not None:q=q.where(InsulationInstall.season_id==season_id)
    return db.scalars(q).all()
@router.post('/insulation-installs')
def install(b:InstallInput,u=Depends(editor),db=Depends(session)):return insulation_service.install(db,b,u)
@router.put('/insulation-installs/{key}/ventilation')
def ventilation(key:int,b:VentilationInput,u=Depends(editor),db=Depends(session)):return insulation_service.change(db,key,b,u,'ventilation')
@router.post('/insulation-installs/{key}/accept')
def accept(key:int,u=Depends(admin),db=Depends(session)):return insulation_service.change(db,key,None,u,'accept')
@router.post('/insulation-installs/{key}/remove')
def remove(key:int,b:RemoveInput,u=Depends(editor),db=Depends(session)):return insulation_service.change(db,key,b,u,'remove')
@router.get('/spring-reviews')
def reviews(season_id:int|None=None,u=Depends(current),db=Depends(session)):
    q=select(SpringReview).order_by(SpringReview.id.desc())
    if season_id is not None:q=q.where(SpringReview.season_id==season_id)
    return db.scalars(q).all()
@router.post('/spring-reviews')
def review(b:SpringInput,u=Depends(editor),db=Depends(session)):return spring_service.record(db,b,u)
@router.post('/spring-reviews/{key}/pass')
def pass_review(key:int,b:PassInput,u=Depends(admin),db=Depends(session)):return spring_service.pass_review(db,key,b,u)
