import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=Path('/tmp')/f"apiary-test-{os.getpid()}.db"
os.environ['DATABASE_URL']=os.getenv('TEST_DATABASE_URL') or f'sqlite:///{DB}'
os.environ['SEED_DEMO']='false'
os.environ['REDIS_URL']='redis://127.0.0.1:6399/0'
import sys
sys.path.insert(0,str(ROOT))

import pytest
from fastapi.testclient import TestClient

try:
    import fakeredis
except ImportError:  # optional test dependency
    fakeredis=None
import src.app as app_module
import src.worker as worker_module
if fakeredis is not None:
    app_module.queue=fakeredis.FakeRedis(decode_responses=True)
    worker_module.queue=app_module.queue
from src.app import app
from src.database import engine,Base,Session
from src.models import User
from src.auth import hash_password

PASSWORD='Hive2026!'


@pytest.fixture(scope='session')
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:yield c


@pytest.fixture(scope='session',autouse=True)
def accounts(client):
    with Session() as db:
        for role in ['admin','beekeeper','viewer']:
            if not db.query(User).filter_by(email=f'{role}@shanjing.test').first():
                db.add(User(email=f'{role}@shanjing.test',password=hash_password(PASSWORD),role=role))
        db.commit()
