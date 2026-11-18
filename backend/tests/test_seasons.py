import os,uuid,threading
import pytest
from datetime import date
from sqlalchemy.exc import IntegrityError
from src.database import Session
from src.models import Hive,Visit,CareAction,Season
from src.resource_models import FeedLot
from src.season_models import SpringReview,InsulationInstall,InsulationLot
from src.worker import apply_visit,recover
from .helpers import auth,make_hive,make_visit,rollover

POSTGRES_ONLY=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='并发行锁需真实 PostgreSQL')


def active(db):
    return db.query(Season).filter_by(state='active').one()


def set_status(visit_id,state):
    with Session() as db:
        db.get(Visit,visit_id).status=state;db.commit()


def plan_care(client,visit_id,kind='feed',kg=1.0):
    return client.post('/care',json={'visit_id':visit_id,'kind':kind,'feed_kg':kg},headers=auth(client))


def closed_season_id(client):
    return [s['id'] for s in client.get('/seasons',headers=auth(client)).json() if s['state']=='closed'][0]


def test_history_is_migrated_into_first_season(client):
    with Session() as db:
        assert active(db).code=='2026-winter'
        assert db.query(Visit).filter(Visit.season_id.is_(None)).count()==0
        assert db.query(CareAction).filter(CareAction.season_id.is_(None)).count()==0
    assert client.get('/seasons',headers=auth(client)).json()[-1]['code']=='2026-winter'


def test_rollover_blocked_by_open_care(client):
    hive=make_hive(client,'H-910')
    visit=make_visit(client,hive['id'])
    set_status(visit['id'],'screened')
    assert plan_care(client,visit['id']).status_code==200
    preview=client.get('/seasons/rollover/preview',headers=auth(client)).json()
    assert preview['can_close'] is False and any(b['kind']=='care' for b in preview['blockers'])
    blocked=rollover(client)
    assert blocked.status_code==409 and blocked.json()['detail']['blockers']
    with Session() as db:
        care=db.query(CareAction).filter_by(visit_id=visit['id']).one()
        care.status='closed';row=db.get(Visit,visit['id']);row.status='closed'
        db.get(Hive,row.hive_id).care_state='winter_ready'
        db.commit()


def test_rollover_blocked_by_unfinished_screening(client):
    hive=make_hive(client,'H-911')
    visit=make_visit(client,hive['id'])
    set_status(visit['id'],'screening')
    blocked=rollover(client)
    assert blocked.status_code==409
    assert any(b['kind']=='screening' and b['code']==visit['code'] for b in blocked.json()['detail']['blockers'])
    set_status(visit['id'],'recorded')


def test_rollover_blocked_by_move_in_transit(client):
    hive=make_hive(client,'H-912')
    with Session() as db:
        row=db.get(Hive,hive['id']);row.care_state='winter_ready';db.commit()
    created=client.post('/moves',json={'hive_id':hive['id'],'destination':'南麓春繁场','move_date':'2026-12-01','health_note':'箱体清洁，未见螨害与幼虫症状'},headers=auth(client))
    assert created.status_code==200,created.text
    move=created.json()
    blocked=rollover(client)
    assert blocked.status_code==409
    assert any(b['kind']=='move' and b['code']==f"MOVE-{move['id']}" for b in blocked.json()['detail']['blockers'])
    assert client.post(f"/moves/{move['id']}/cancel",headers=auth(client)).status_code==200


def test_blocked_rollover_leaves_active_season_untouched(client):
    hive=make_hive(client,'H-915')
    visit=make_visit(client,hive['id'])
    set_status(visit['id'],'screening')
    before=client.get('/seasons/current',headers=auth(client)).json()
    assert rollover(client).status_code==409
    after=client.get('/seasons/current',headers=auth(client)).json()
    assert after['id']==before['id'] and after['state']=='active'
    set_status(visit['id'],'screened')


def test_rollover_seals_old_and_starts_new_season(client):
    old=client.get('/seasons/current',headers=auth(client)).json()
    opened=rollover(client,'open-'+uuid.uuid4().hex,'2027—2028 越冬季')
    assert opened.status_code==200,opened.text
    body=opened.json()
    assert body['state']=='active' and body['previous_season_id']==old['id']
    assert body['code'].startswith('2027-winter')
    seasons=client.get('/seasons',headers=auth(client)).json()
    assert seasons[0]['id']==body['id']
    closed=[s for s in seasons if s['id']==old['id']][0]
    assert closed['state']=='closed' and closed['summary']['visits']>=1
    with Session() as db:
        assert db.query(Season).filter_by(state='active').count()==1
        assert all(h.care_state=='awaiting_inspection' for h in db.query(Hive).all())


def test_sealed_season_is_read_only_and_new_season_can_inspect_same_hive(client):
    hive=make_hive(client,'H-913')
    seasons=client.get('/seasons',headers=auth(client)).json()
    old_id=[s['id'] for s in seasons if s['state']=='closed'][0];new_id=seasons[0]['id']
    with Session() as db:
        old_visit=Visit(code='V-OLD-'+uuid.uuid4().hex[:6],hive_id=hive['id'],season_id=old_id,weight_kg=24.0,temperature=33.0,activity=50.0,feed_left=2.0,queen_seen=True,colony_frames=8,status='recorded')
        db.add(old_visit);db.commit();old_visit_id=old_visit.id
    assert client.post(f'/visits/{old_visit_id}/screen',headers=auth(client)).status_code==409
    new_visit=make_visit(client,hive['id'])
    visits=client.get(f'/visits?season_id={new_id}',headers=auth(client)).json()
    old_visits=client.get(f'/visits?season_id={old_id}',headers=auth(client)).json()
    assert any(v['id']==new_visit['id'] for v in visits) and all(v['season_id']==new_id for v in visits)
    assert all(v['id']!=new_visit['id'] and v['season_id']==old_id for v in old_visits)


def test_sealed_season_rejects_care_writes(client):
    hive=make_hive(client,'H-916')
    old_id=closed_season_id(client)
    with Session() as db:
        visit=Visit(code='V-OLD-CARE-'+uuid.uuid4().hex[:6],hive_id=hive['id'],season_id=old_id,weight_kg=24.0,temperature=33.0,activity=50.0,feed_left=2.0,queen_seen=True,colony_frames=8,status='screened')
        db.add(visit);db.commit();visit_id=visit.id
    assert plan_care(client,visit_id).status_code==409
    with Session() as db:
        care=CareAction(visit_id=visit_id,season_id=old_id,kind='feed',feed_kg=1.0,status='executed')
        db.add(care);db.commit();care_id=care.id
    assert client.post(f'/care/{care_id}/execute',json={'queen_installed':False},headers=auth(client)).status_code==409
    assert client.post(f'/care/{care_id}/followup',json={'followup_weight':24.0,'followup_queen':True,'followup_frames':8},headers=auth(client)).status_code==409
    assert client.post(f'/care/{care_id}/close',headers=auth(client)).status_code==409


def test_same_hive_can_have_spring_review_in_new_season(client):
    hive=make_hive(client,'H-917')
    seasons=client.get('/seasons',headers=auth(client)).json()
    old_id=[s['id'] for s in seasons if s['state']=='closed'][0];new_id=seasons[0]['id']
    with Session() as db:
        lot=InsulationLot(code='IN-TEST-'+uuid.uuid4().hex[:6],available_units=10);db.add(lot);db.flush()
        old_install=InsulationInstall(hive_id=hive['id'],season_id=old_id,lot_id=lot.id,units=2,ventilation_checked=True,state='accepted',installed_by='old')
        db.add(old_install);db.flush()
        db.add(SpringReview(hive_id=hive['id'],season_id=old_id,install_id=old_install.id,opening_weight=27.0,frames=7,queen_seen=True,mortality_pct=8.0,winter_snapshot={},rescue_after_care_id=0,state='passed',passed_by='old'))
        db.add(InsulationInstall(hive_id=hive['id'],season_id=new_id,lot_id=lot.id,units=2,ventilation_checked=True,state='accepted',installed_by='new'))
        db.get(Hive,hive['id']).care_state='winter_ready'
        db.commit()
    created=client.post('/spring-reviews',json={'hive_id':hive['id'],'opening_weight':26.0,'frames':7,'queen_seen':True,'mortality_pct':9.0},headers=auth(client))
    assert created.status_code==200,created.text
    assert created.json()['season_id']==new_id
    with Session() as db:
        assert db.query(SpringReview).filter_by(hive_id=hive['id']).count()==2


def test_late_screening_keeps_new_season_hive_state(client):
    hive=make_hive(client,'H-914')
    old_id=closed_season_id(client)
    with Session() as db:
        row=db.get(Hive,hive['id'])
        visit=Visit(code='V-LATE-'+uuid.uuid4().hex[:6],hive_id=row.id,season_id=old_id,weight_kg=24.0,temperature=33.0,activity=50.0,feed_left=2.0,queen_seen=False,colony_frames=8,status='screening')
        db.add(visit);db.commit();visit_id=visit.id;before=row.care_state
    with Session() as db:
        assert apply_visit(db,visit_id) is not None
    with Session() as db:
        assert db.get(Hive,hive['id']).care_state==before
        assert db.get(Visit,visit_id).anomaly_score is not None


def test_interrupted_screening_is_recoverable(client):
    hive=make_hive(client,'H-918')
    visit=make_visit(client,hive['id'])
    set_status(visit['id'],'screening')
    recover()
    with Session() as db:
        assert db.get(Visit,visit['id']).status=='blocked'
    assert client.post(f"/visits/{visit['id']}/screen",headers=auth(client)).status_code==200
    set_status(visit['id'],'screened')


def test_new_season_can_repeat_full_care_cycle(client):
    hive=make_hive(client,'H-919')
    visit=make_visit(client,hive['id'])
    set_status(visit['id'],'screened')
    care=plan_care(client,visit['id'],'feed',1.5).json()
    with Session() as db:
        lot=FeedLot(code='FD-TEST-'+uuid.uuid4().hex[:6],received_kg=10.0,available_kg=10.0,expires_on=date(2027,11,30),state='active')
        db.add(lot);db.commit();lot_id=lot.id
    assert client.post('/feed-issues',json={'care_id':care['id'],'lot_id':lot_id},headers=auth(client)).status_code==200
    assert client.post(f"/care/{care['id']}/execute",json={'queen_installed':False},headers=auth(client)).status_code==200
    assert client.post(f"/care/{care['id']}/followup",json={'followup_weight':24.5,'followup_queen':True,'followup_frames':8},headers=auth(client)).status_code==200
    assert client.post(f"/care/{care['id']}/close",headers=auth(client)).status_code==200
    assert client.get('/seasons/rollover/preview',headers=auth(client)).json()['can_close'] is True


def test_retry_with_same_request_returns_same_season(client):
    request='retry-'+uuid.uuid4().hex
    first=rollover(client,request,'2028—2029 越冬季')
    assert first.status_code==200,first.text
    before=len(client.get('/seasons',headers=auth(client)).json())
    retried=[rollover(client,request,'2028—2029 越冬季') for _ in range(3)]
    assert all(r.status_code==200 for r in retried)
    assert {r.json()['id'] for r in retried}=={first.json()['id']}
    assert len(client.get('/seasons',headers=auth(client)).json())==before


def test_database_allows_only_one_active_season(client):
    with Session() as db:
        db.add(Season(code='dup-'+uuid.uuid4().hex[:6],label='重复开季',state='active'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


@POSTGRES_ONLY
def test_parallel_rollovers_open_exactly_one_season(client):
    with Session() as db:
        before=db.query(Season).count()
    results=[];barrier=threading.Barrier(2)

    def attempt(tag):
        headers=auth(client);barrier.wait()
        results.append(client.post('/seasons/rollover',json={'request_id':f'race-{tag}-{uuid.uuid4().hex}','label':f'并发开季 {tag}'},headers=headers))

    threads=[threading.Thread(target=attempt,args=(tag,)) for tag in ['a','b']]
    for t in threads:t.start()
    for t in threads:t.join()
    assert sorted(r.status_code for r in results)==[200,409],[(r.status_code,r.text) for r in results]
    with Session() as db:
        assert db.query(Season).filter_by(state='active').count()==1
        assert db.query(Season).count()==before+1


@POSTGRES_ONLY
def test_parallel_same_request_opens_once(client):
    request='same-'+uuid.uuid4().hex
    before=len(client.get('/seasons',headers=auth(client)).json())
    results=[];barrier=threading.Barrier(2)

    def attempt():
        headers=auth(client);barrier.wait()
        results.append(client.post('/seasons/rollover',json={'request_id':request,'label':'并发同回执 越冬季'},headers=headers))

    threads=[threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:t.start()
    for t in threads:t.join()
    assert [r.status_code for r in results]==[200,200]
    assert len({r.json()['id'] for r in results})==1
    assert len(client.get('/seasons',headers=auth(client)).json())==before+1
