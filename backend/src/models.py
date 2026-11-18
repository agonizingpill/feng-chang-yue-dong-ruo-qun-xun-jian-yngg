from datetime import datetime
from sqlalchemy import String,Float,Boolean,ForeignKey,JSON,CheckConstraint,DateTime,func
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    email:Mapped[str]=mapped_column(String(120),unique=True)
    password:Mapped[str]=mapped_column(String(240))
    role:Mapped[str]=mapped_column(String(20))
class Hive(Base):
    __tablename__='hives'
    __table_args__=(CheckConstraint('colony_frames>=0 AND colony_frames<=20'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(30),unique=True)
    site:Mapped[str]=mapped_column(String(50))
    queen_present:Mapped[bool]=mapped_column(Boolean)
    colony_frames:Mapped[int]=mapped_column()
    care_state:Mapped[str]=mapped_column(String(30),default='observe')
class Visit(Base):
    __tablename__='visits'
    __table_args__=(CheckConstraint('weight_kg>0 AND activity>=0 AND feed_left>=0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(50),unique=True)
    hive_id:Mapped[int]=mapped_column(ForeignKey('hives.id'))
    weight_kg:Mapped[float]=mapped_column(Float)
    temperature:Mapped[float]=mapped_column(Float)
    activity:Mapped[float]=mapped_column(Float)
    feed_left:Mapped[float]=mapped_column(Float)
    queen_seen:Mapped[bool]=mapped_column(Boolean)
    colony_frames:Mapped[int]=mapped_column()
    anomaly_score:Mapped[float|None]=mapped_column(Float,nullable=True)
    anomaly_flag:Mapped[bool|None]=mapped_column(Boolean,nullable=True)
    decision_margin:Mapped[float|None]=mapped_column(Float,nullable=True)
    model_evidence:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    status:Mapped[str]=mapped_column(String(30),default='recorded')
    recorded_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
class CareAction(Base):
    __tablename__='care_actions'
    __table_args__=(CheckConstraint('feed_kg>=0 AND feed_kg<=3'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    visit_id:Mapped[int]=mapped_column(ForeignKey('visits.id'))
    kind:Mapped[str]=mapped_column(String(20))
    feed_kg:Mapped[float]=mapped_column(Float,default=0)
    status:Mapped[str]=mapped_column(String(30),default='planned')
    queen_installed:Mapped[bool]=mapped_column(Boolean,default=False)
    followup_weight:Mapped[float|None]=mapped_column(Float,nullable=True)
    followup_queen:Mapped[bool|None]=mapped_column(Boolean,nullable=True)
    followup_frames:Mapped[int|None]=mapped_column(nullable=True)
    executed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    closed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class Audit(Base):
    __tablename__='audits'
    id:Mapped[int]=mapped_column(primary_key=True)
    actor:Mapped[str]=mapped_column(String(120))
    action:Mapped[str]=mapped_column(String(240))
    at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
