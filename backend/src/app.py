import os,json,time,logging
from contextlib import asynccontextmanager
import redis
from sqlalchemy import select,text
from sqlalchemy.exc import IntegrityError
from fastapi import FastAPI,Depends,HTTPException,Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .database import Base,engine,session
from .models import User,Hive,Visit,CareAction,Audit
from .schemas import Login,HiveInput,VisitInput,CareInput,ExecutionInput,FollowupInput
from .auth import current,editor,admin,hash_password,issue
from .yard_service import save_hive,record_visit,enqueue_screen,require
from . import care_service
from .screen_model import reference_model
from .resource_routes import router as resources
from .season_routes import router as seasons
queue=redis.Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'),decode_responses=True)
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if os.getenv('SEED_DEMO','true').lower()=='true':
        try:
            from scripts.seed_demo import seed
            seed()
        except Exception:logging.exception('seed failed')
    yield
app=FastAPI(title='山荆蜂业 · 越冬弱群巡检',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:18226'],allow_headers=['*'],allow_methods=['*'])
@app.middleware('http')
async def timings(request:Request,call_next):
    start=time.monotonic();response=await call_next(request);response.headers['X-Elapsed-Ms']=str(round((time.monotonic()-start)*1000,2));return response
@app.middleware('http')
async def recover(request:Request,call_next):
    try:return await call_next(request)
    except IntegrityError:return JSONResponse({'detail':'蜂箱/巡检编号或关联冲突，请刷新后重试'},409)
    except Exception:
        logging.exception('request error');return JSONResponse({'detail':'蜂场记录暂时无法保存，请重试'},500)
app.include_router(resources);app.include_router(seasons)
@app.get('/health')
def health(db=Depends(session)):db.execute(text('SELECT 1'));queue.ping();return {'status':'ok'}
@app.post('/auth/login')
def login(body:Login,db=Depends(session)):
    user=db.scalar(select(User).where(User.email==body.email))
    if not user or user.password!=hash_password(body.password):raise HTTPException(401,'邮箱或密码错误')
    return {'token':issue(user),'email':user.email,'role':user.role}
@app.get('/hives')
def hives(user=Depends(current),db=Depends(session)):return db.scalars(select(Hive).order_by(Hive.id)).all()
@app.post('/hives')
def add_hive(body:HiveInput,user=Depends(admin),db=Depends(session)):return save_hive(db,body,user)
@app.put('/hives/{key}')
def edit_hive(key:int,body:HiveInput,user=Depends(admin),db=Depends(session)):return save_hive(db,body,user,key)
@app.get('/visits')
def visits(user=Depends(current),db=Depends(session)):return db.scalars(select(Visit).order_by(Visit.id.desc())).all()
@app.get('/visits/{key}')
def visit(key:int,user=Depends(current),db=Depends(session)):return require(db,Visit,key)
@app.post('/visits')
def record(body:VisitInput,user=Depends(editor),db=Depends(session)):return record_visit(db,body,user)
@app.post('/visits/{key}/screen')
def screen_one(key:int,user=Depends(editor),db=Depends(session)):return enqueue_screen(db,user,queue,key)
@app.post('/screening')
def screen_yard(user=Depends(editor),db=Depends(session)):return enqueue_screen(db,user,queue)
@app.get('/screening/{jobid}')
def screening_result(jobid:str,user=Depends(current)):
    result=queue.get('apiary:screen:'+jobid)
    if not result:raise HTTPException(404,'筛查结果已过期，请重新筛查')
    return json.loads(result)
@app.get('/winter-reference')
def reference(user=Depends(current)):return reference_model()[1]
@app.get('/care')
def care(user=Depends(current),db=Depends(session)):return db.scalars(select(CareAction).order_by(CareAction.id.desc())).all()
@app.post('/care')
def plan(body:CareInput,user=Depends(editor),db=Depends(session)):return care_service.plan(db,body,user)
@app.post('/care/{key}/execute')
def execute(key:int,body:ExecutionInput,user=Depends(editor),db=Depends(session)):return care_service.execute(db,key,body,user)
@app.post('/care/{key}/followup')
def followup(key:int,body:FollowupInput,user=Depends(editor),db=Depends(session)):return care_service.followup(db,key,body,user)
@app.post('/care/{key}/close')
def close(key:int,user=Depends(admin),db=Depends(session)):return care_service.close(db,key,user)
@app.get('/audits')
def audits(user=Depends(current),db=Depends(session)):return db.scalars(select(Audit).order_by(Audit.id.desc()).limit(60)).all()
