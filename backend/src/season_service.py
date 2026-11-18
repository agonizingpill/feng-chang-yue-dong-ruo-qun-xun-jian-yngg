import re
from datetime import datetime
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from .models import Season,Hive,Visit,CareAction
from .season_models import ApiaryMove,InsulationInstall,SpringReview
from .resource_models import FeedIssue

LEGACY_CODE='2026-winter'
LEGACY_LABEL='2026—2027 越冬季'
# Work still in flight blocks closing. These are the same "active care" states
# the move and spring guards use; needs_requeen is the historical superseded
# record (a new requeen care carries the work) and cancelled is terminal.
BLOCKED_CARE={'planned':'待执行','executed':'已执行待复查','rechecked':'复查待关闭'}
BLOCKED_MOVE={'requested':'待主管检疫签发','approved':'已签发尚未到站'}
BLOCKED_SCREEN={'screening'}


def latest_season(db):
    """Newest season; only an empty database creates the legacy first season."""
    row=db.scalar(select(Season).order_by(Season.id.desc()))
    if row:return row
    row=Season(code=LEGACY_CODE,label=LEGACY_LABEL,state='active',opened_by='system')
    db.add(row);db.flush();return row


def active_season(db):
    return db.scalar(select(Season).where(Season.state=='active').order_by(Season.id)) or latest_season(db)


def active_season_shared(db):
    """Shared-lock the active season so a rollover cannot interleave with a write.

    If the lock wait ends because another admin sealed the season, the locked
    statement no longer matches; a fresh statement then sees the new season
    instead of silently falling back to the sealed first row.
    """
    row=db.scalar(select(Season).where(Season.state=='active').order_by(Season.id).with_for_update(read=True))
    if row is None:row=db.scalar(select(Season).where(Season.state=='active').order_by(Season.id))
    return row or latest_season(db)


def ensure_writable(db,season_id,what='记录'):
    season=active_season_shared(db)
    if season_id is None or season_id!=season.id:
        raise HTTPException(409,f'{what}属于已封存的越冬季，旧季只读；请在新季“{season.label}”重新办理')
    if season.state!='active':
        raise HTTPException(409,'当前没有进行中的越冬季，暂不能登记，请联系主管核对季档')
    return season


def blockers(db,season):
    """Everything that must finish before this season can be sealed."""
    items=[]
    rows=db.execute(select(CareAction,Visit,Hive).join(Visit,CareAction.visit_id==Visit.id).join(Hive,Visit.hive_id==Hive.id).where(CareAction.season_id==season.id,CareAction.status.in_(list(BLOCKED_CARE))).order_by(CareAction.id)).all()
    for care,visit,hive in rows:
        items.append({'kind':'care','id':care.id,'hive':hive.code,'code':f'CARE-{care.id}','state':care.status,'message':f'{hive.code} 处置 CARE-{care.id} 尚在进行（{BLOCKED_CARE[care.status]}）'})
    rows=db.execute(select(ApiaryMove,Hive).join(Hive,ApiaryMove.hive_id==Hive.id).where(ApiaryMove.season_id==season.id,ApiaryMove.state.in_(list(BLOCKED_MOVE))).order_by(ApiaryMove.id)).all()
    for move,hive in rows:
        items.append({'kind':'move','id':move.id,'hive':hive.code,'code':f'MOVE-{move.id}','state':move.state,'message':f'{hive.code} 转场 MOVE-{move.id} 未到站（{BLOCKED_MOVE[move.state]}）'})
    rows=db.execute(select(Visit,Hive).join(Hive,Visit.hive_id==Hive.id).where(Visit.season_id==season.id,Visit.status.in_(list(BLOCKED_SCREEN))).order_by(Visit.id)).all()
    for visit,hive in rows:
        items.append({'kind':'screening','id':visit.id,'hive':hive.code,'code':visit.code,'state':visit.status,'message':f'{hive.code} 巡检 {visit.code} 筛查尚未结束'})
    return items


def preview(db):
    season=db.scalar(select(Season).where(Season.state=='active').order_by(Season.id))
    if not season:return {'season':None,'blockers':[],'can_close':False}
    items=blockers(db,season)
    return {'season':season,'blockers':items,'can_close':not items}


def summary(db,season):
    def count(model):
        return db.scalar(select(func.count()).select_from(model).where(model.season_id==season.id)) or 0
    return {'visits':count(Visit),'care_actions':count(CareAction),'moves':count(ApiaryMove),'insulation_installs':count(InsulationInstall),'spring_reviews':count(SpringReview),
            'feed_issues':db.scalar(select(func.count()).select_from(FeedIssue).join(CareAction,FeedIssue.care_id==CareAction.id).where(CareAction.season_id==season.id)) or 0}


def next_identity(db,season,label):
    years=[int(x) for x in re.findall(r'(?<!\d)(\d{4})(?!\d)',season.code or '')]
    year=(years[0] if years else datetime.utcnow().year)+1
    code=f'{year}-winter';suffix=2
    while db.scalar(select(Season.id).where(Season.code==code)):
        code=f'{year}-winter-{suffix}';suffix+=1
    return code,(label or f'{year}—{year+1} 越冬季')


def _by_request(db,request_id):
    if not request_id:return None
    return db.scalar(select(Season).where(Season.open_request_id==request_id))


def rollover(db,body,user):
    """Seal the active season and open the next one. Safe under retries and races.

    - A retried request (same request_id, e.g. lost receipt) returns the season
      that the first attempt opened instead of opening another one.
    - The active row is locked; a concurrent close either waits and then sees a
      non-active season, or loses the unique partial index and re-reads.
    """
    request_id=body.request_id
    label=body.label.strip()
    done=_by_request(db,request_id)
    if done:return done
    season=db.scalar(select(Season).where(Season.state=='active').order_by(Season.id).with_for_update())
    if not season:
        done=_by_request(db,request_id)
        if done:return done
        if db.scalar(select(Season.id)):
            raise HTTPException(409,'另一主管已完成结季，请刷新查看新季')
        raise HTTPException(409,'当前没有进行中的越冬季，无法结季')
    done=_by_request(db,request_id)
    if done:return done
    if season.state!='active':
        raise HTTPException(409,'另一主管已完成结季，请刷新查看新季')
    items=blockers(db,season)
    if items:
        raise HTTPException(409,{'message':f'尚有{len(items)}项未结束，暂不能结季','blockers':items})
    archived=summary(db,season)
    season.state='closed';season.closed_by=user.email;season.closed_at=datetime.utcnow();season.summary=archived
    try:
        db.flush()
        code,title=next_identity(db,season,label)
        opened=Season(code=code,label=title,state='active',previous_season_id=season.id,open_request_id=request_id,opened_by=user.email,summary={'started_from':'awaiting_inspection'})
        db.add(opened);db.flush()
        waiting=0
        for hive in db.scalars(select(Hive).order_by(Hive.id).with_for_update()).all():
            if hive.care_state!='awaiting_inspection':
                hive.care_state='awaiting_inspection';waiting+=1
        from .yard_service import audit
        audit(db,user,f'主管结季 {season.code}→{opened.code}，旧季封存，{waiting}箱回到待巡检')
        db.commit()
    except IntegrityError:
        # Lost the race (same request id or the single-active index): the other
        # attempt's season is the answer, so a retry never opens a second one.
        db.rollback()
        done=_by_request(db,request_id)
        if done:return done
        raise HTTPException(409,'另一主管已完成结季，请刷新查看新季')
    return opened
