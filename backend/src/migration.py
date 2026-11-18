from sqlalchemy import inspect,text
from .database import engine
from .models import Season

SEASON_TABLES=('visits','care_actions','apiary_moves','insulation_installs','spring_reviews')


def _legacy_season(conn):
    row=conn.execute(text('SELECT id FROM seasons ORDER BY id LIMIT 1')).first()
    if row:return row[0]
    conn.execute(text("INSERT INTO seasons (code,label,state,opened_by) VALUES ('2026-winter','2026—2027 越冬季','active','system')"))
    return conn.execute(text('SELECT id FROM seasons ORDER BY id LIMIT 1')).scalar()


def _column_exists(conn,table,column):
    return any(c['name']==column for c in inspect(conn).get_columns(table))


def migrate():
    """Idempotent start-up backfill: attach every historical row to the first season.

    Runs after create_all, so a fresh database already has season_id. An existing
    database gets the column added and backfilled in one transaction: a crash
    leaves the old schema untouched and the next start simply retries.
    """
    Season.__table__.create(bind=engine,checkfirst=True)
    inspector=inspect(engine)
    tables=set(inspector.get_table_names())
    dialect=engine.dialect.name
    with engine.begin() as conn:
        season_id=_legacy_season(conn)
        for table in SEASON_TABLES:
            if table not in tables:continue
            if not _column_exists(conn,table,'season_id'):
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN season_id INTEGER REFERENCES seasons(id)'))
            conn.execute(text(f'UPDATE {table} SET season_id=:sid WHERE season_id IS NULL'),{'sid':season_id})
            if dialect=='postgresql':
                conn.execute(text(f'ALTER TABLE {table} ALTER COLUMN season_id SET NOT NULL'))
            conn.execute(text(f'CREATE INDEX IF NOT EXISTS ix_{table}_season_id ON {table} (season_id)'))
        if dialect=='postgresql' and 'spring_reviews' in tables:
            conn.execute(text('ALTER TABLE spring_reviews DROP CONSTRAINT IF EXISTS spring_reviews_hive_id_key'))
            conn.execute(text('ALTER TABLE spring_reviews DROP CONSTRAINT IF EXISTS uq_spring_review_season_hive'))
            conn.execute(text('ALTER TABLE spring_reviews ADD CONSTRAINT uq_spring_review_season_hive UNIQUE (season_id,hive_id)'))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_seasons_one_active ON seasons (state) WHERE state='active'"))
