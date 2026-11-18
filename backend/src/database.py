import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase,sessionmaker
engine=create_engine(os.getenv('DATABASE_URL','postgresql+psycopg://apiary:apiary@db:5432/apiary'),pool_pre_ping=True)
Session=sessionmaker(engine,expire_on_commit=False)
class Base(DeclarativeBase):pass
def session():
    with Session() as db:yield db
