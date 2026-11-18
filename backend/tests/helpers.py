import uuid
import pytest
from src.database import Session
from src.models import Hive,Visit,CareAction,Season

PASSWORD='Hive2026!'


def auth(client,role='admin'):
    r=client.post('/auth/login',json={'email':f'{role}@shanjing.test','password':PASSWORD})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}


def make_hive(client,code='H-900'):
    r=client.post('/hives',json={'code':code,'site':'测试场','queen_present':True,'colony_frames':8},headers=auth(client))
    assert r.status_code==200,r.text
    return r.json()


def make_visit(client,hive_id,code=None,queen_seen=True,frames=8,weight=24.0):
    body={'code':code or 'V-'+uuid.uuid4().hex[:8],'hive_id':hive_id,'weight_kg':weight,'temperature':33.0,'activity':50.0,'feed_left':2.0,'queen_seen':queen_seen,'colony_frames':frames}
    r=client.post('/visits',json=body,headers=auth(client))
    assert r.status_code==200,r.text
    return r.json()


def rollover(client,request_id=None,label='2027—2028 越冬季'):
    return client.post('/seasons/rollover',json={'request_id':request_id or 'req-'+uuid.uuid4().hex,'label':label},headers=auth(client))
