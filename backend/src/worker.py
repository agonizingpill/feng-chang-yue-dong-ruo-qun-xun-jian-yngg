import os,json,traceback
from pathlib import Path
import redis
from sqlalchemy import select
from .database import Session
from .models import Visit,Hive,Season
from .screen_model import screen,reference_model
from .yard_service import latest
queue=redis.Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'),decode_responses=True)


def apply_visit(db,key):
    """Screen one queued visit inside an open session and commit the result."""
    visit=db.scalar(select(Visit).where(Visit.id==key).with_for_update())
    if not visit or visit.status!='screening':return None
    score,flag,margin,evidence=screen(visit)
    visit.anomaly_score=score;visit.anomaly_flag=flag;visit.decision_margin=margin;visit.model_evidence=evidence;visit.status='screened'
    hive=db.get(Hive,visit.hive_id)
    active=db.scalar(select(Season).where(Season.state=='active').order_by(Season.id))
    # A late result for a sealed season still keeps its score on the old visit,
    # but must never overwrite the new season's hive state.
    if active and active.id==visit.season_id and latest(db,hive.id,visit.season_id)==visit.id:
        hive.care_state='needs_care' if flag or not visit.queen_seen else 'observe'
    db.commit()
    return {'visit_id':visit.id,'hive_id':hive.id,'score':score,'flag':flag}


def process_task(task,store=None):
    points=[];evidence=reference_model()[1]
    for key in task['visit_ids']:
        Path('/tmp/apiary-heartbeat').touch()
        with Session() as db:
            point=apply_visit(db,key)
        if point:points.append(point)
    result={'status':'done','count':len(points),'points':points,'evidence':evidence}
    if store is not None:store(task['job_id'],result)
    return result


def store_result(job_id,result):
    try:
        Path('/artifacts').mkdir(exist_ok=True);Path(f'/artifacts/screen-{job_id}.json').write_text(json.dumps(result))
    except OSError:
        # The artifact volume is a convenience copy; results already committed
        # to visits must not be rolled back or marked blocked because of it.
        traceback.print_exc()
    queue.set('apiary:screen:'+job_id,json.dumps(result),ex=86400)


def recover():
    """Resume after an interruption without losing queued or recorded work.

    Jobs still sitting in Redis are drained and applied; visits left in the
    transient ``screening`` state with no job behind them are returned to the
    retryable ``blocked`` state instead of blocking the season forever.
    """
    while True:
        job=queue.lpop('apiary:screening')
        if not job:break
        task=json.loads(job)
        try:process_task(task,store_result)
        except Exception:
            traceback.print_exc()
    try:
        with Session() as db:
            for visit in db.scalars(select(Visit).where(Visit.status=='screening')).all():
                visit.status='blocked'
            db.commit()
    except Exception:
        # Tables may not exist yet (backend still starting); the next start retries.
        traceback.print_exc()


def main():
    recover()
    while True:
        Path('/tmp/apiary-heartbeat').touch();job=queue.blpop('apiary:screening',timeout=3)
        if not job:continue
        task=json.loads(job[1])
        try:
            process_task(task,store_result)
        except Exception as error:
            traceback.print_exc();queue.set('apiary:screen:'+task['job_id'],json.dumps({'status':'failed','error':str(error)}),ex=86400)
            with Session() as db:
                for v in db.scalars(select(Visit).where(Visit.id.in_(task['visit_ids']),Visit.status=='screening')).all():v.status='blocked'
                db.commit()


if __name__=='__main__':main()
