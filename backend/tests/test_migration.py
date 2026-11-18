import os
import pytest
from sqlalchemy import create_engine,text,inspect
from sqlalchemy.engine import make_url

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='需要真实 PostgreSQL 验证旧库升级')


def test_legacy_database_is_backfilled_into_first_season():
    url=make_url(os.environ['TEST_DATABASE_URL'])
    admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT')
    legacy_name='apiary_legacy_test'
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS {legacy_name} WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE {legacy_name}'))
    legacy_engine=create_engine(url.set(database=legacy_name))
    with legacy_engine.begin() as conn:
        # Schema as it existed before seasons: no seasons table, no season_id.
        conn.execute(text('CREATE TABLE hives (id SERIAL PRIMARY KEY, code VARCHAR(30) UNIQUE NOT NULL, site VARCHAR(50) NOT NULL, queen_present BOOLEAN NOT NULL, colony_frames INTEGER NOT NULL, care_state VARCHAR(30) NOT NULL)'))
        conn.execute(text('CREATE TABLE visits (id SERIAL PRIMARY KEY, code VARCHAR(50) UNIQUE NOT NULL, hive_id INTEGER REFERENCES hives(id), weight_kg FLOAT NOT NULL, temperature FLOAT NOT NULL, activity FLOAT NOT NULL, feed_left FLOAT NOT NULL, queen_seen BOOLEAN NOT NULL, colony_frames INTEGER NOT NULL, anomaly_score FLOAT, anomaly_flag BOOLEAN, decision_margin FLOAT, model_evidence JSON, status VARCHAR(30) NOT NULL, recorded_at TIMESTAMP)'))
        conn.execute(text('CREATE TABLE care_actions (id SERIAL PRIMARY KEY, visit_id INTEGER REFERENCES visits(id), kind VARCHAR(20) NOT NULL, feed_kg FLOAT NOT NULL, status VARCHAR(30) NOT NULL, queen_installed BOOLEAN NOT NULL, followup_weight FLOAT, followup_queen BOOLEAN, followup_frames INTEGER, executed_at TIMESTAMP, closed_at TIMESTAMP)'))
        conn.execute(text('CREATE TABLE spring_reviews (id SERIAL PRIMARY KEY, hive_id INTEGER UNIQUE REFERENCES hives(id), install_id INTEGER NOT NULL, opening_weight FLOAT NOT NULL, frames INTEGER NOT NULL, queen_seen BOOLEAN NOT NULL, mortality_pct FLOAT NOT NULL, winter_snapshot JSON NOT NULL, rescue_after_care_id INTEGER NOT NULL, rescue_care_id INTEGER UNIQUE REFERENCES care_actions(id), state VARCHAR(24) NOT NULL, resolution VARCHAR(400) NOT NULL, passed_by VARCHAR(120) NOT NULL, created_at TIMESTAMP)'))
        conn.execute(text("INSERT INTO hives (code,site,queen_present,colony_frames,care_state) VALUES ('H-001','东坡',true,8,'winter_ready')"))
        conn.execute(text("INSERT INTO visits (code,hive_id,weight_kg,temperature,activity,feed_left,queen_seen,colony_frames,status) VALUES ('V-OLD-1',1,24,33,50,2,true,8,'closed')"))
        conn.execute(text("INSERT INTO care_actions (visit_id,kind,feed_kg,status,queen_installed) VALUES (1,'feed',1.5,'closed',false)"))
        conn.execute(text("INSERT INTO spring_reviews (hive_id,install_id,opening_weight,frames,queen_seen,mortality_pct,winter_snapshot,rescue_after_care_id,state,resolution,passed_by) VALUES (1,1,24,7,true,8,'{}',0,'passed','历史春检','主管')"))
    import src.migration as migration
    old_engine=migration.engine
    migration.engine=legacy_engine
    try:
        migration.migrate()
        migration.migrate()
    finally:
        migration.engine=old_engine
    try:
        insp=inspect(legacy_engine)
        assert 'seasons' in insp.get_table_names()
        with legacy_engine.connect() as conn:
            season=conn.execute(text('SELECT * FROM seasons')).mappings().one()
            assert season['code']=='2026-winter'
            assert season['state']=='active'
            assert conn.execute(text('SELECT season_id FROM visits')).scalar()==season['id']
            assert conn.execute(text('SELECT season_id FROM care_actions')).scalar()==season['id']
            assert conn.execute(text('SELECT season_id FROM spring_reviews')).scalar()==season['id']
            # history relationships stay intact
            assert conn.execute(text('SELECT h.code FROM care_actions c JOIN visits v ON v.id=c.visit_id JOIN hives h ON h.id=v.hive_id')).scalar()=='H-001'
        # the old per-hive uniqueness is replaced by per-season uniqueness
        uniques={u['name']:u['column_names'] for u in insp.get_unique_constraints('spring_reviews')}
        assert uniques.get('uq_spring_review_season_hive')==['season_id','hive_id']
        assert 'spring_reviews_hive_id_key' not in uniques
    finally:
        legacy_engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS {legacy_name} WITH (FORCE)'))
        admin.dispose()
