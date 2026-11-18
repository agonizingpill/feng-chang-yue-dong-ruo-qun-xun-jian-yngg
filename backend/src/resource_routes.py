from fastapi import APIRouter,Depends
from sqlalchemy import select
from .database import session
from .auth import current,editor,admin
from .resource_models import FeedLot,FeedIssue,QueenObservation
from .resource_schemas import LotInput,LotState,IssueInput,CancelInput,QueenInput
from . import feed_service,queen_service
router=APIRouter()
@router.get('/feed-lots')
def lots(user=Depends(current),db=Depends(session)):return db.scalars(select(FeedLot).order_by(FeedLot.id.desc())).all()
@router.post('/feed-lots')
def receive(body:LotInput,user=Depends(editor),db=Depends(session)):return feed_service.receive(db,body,user)
@router.put('/feed-lots/{key}/state')
def state(key:int,body:LotState,user=Depends(admin),db=Depends(session)):return feed_service.state(db,key,body,user)
@router.get('/feed-issues')
def issues(user=Depends(current),db=Depends(session)):return db.scalars(select(FeedIssue).order_by(FeedIssue.id.desc())).all()
@router.post('/feed-issues')
def issue(body:IssueInput,user=Depends(editor),db=Depends(session)):return feed_service.issue(db,body,user)
@router.post('/care/{key}/cancel')
def cancel(key:int,body:CancelInput,user=Depends(editor),db=Depends(session)):return feed_service.cancel(db,key,body,user)
@router.get('/queen-observations')
def observations(user=Depends(current),db=Depends(session)):return db.scalars(select(QueenObservation).order_by(QueenObservation.id.desc())).all()
@router.post('/queen-observations')
def observe(body:QueenInput,user=Depends(editor),db=Depends(session)):return queen_service.observe(db,body,user)
@router.put('/queen-observations/{key}')
def revise(key:int,body:QueenInput,user=Depends(editor),db=Depends(session)):return queen_service.observe(db,body,user,key)
@router.post('/queen-observations/{key}/confirm')
def confirm(key:int,user=Depends(admin),db=Depends(session)):return queen_service.confirm(db,key,user)
