from datetime import date,datetime
from sqlalchemy import String,Float,Date,DateTime,ForeignKey,Boolean,CheckConstraint,func
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class FeedLot(Base):
    __tablename__='feed_lots'
    __table_args__=(CheckConstraint('received_kg>0 AND available_kg>=0 AND available_kg<=received_kg'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(50),unique=True)
    received_kg:Mapped[float]=mapped_column(Float)
    available_kg:Mapped[float]=mapped_column(Float)
    expires_on:Mapped[date]=mapped_column(Date)
    state:Mapped[str]=mapped_column(String(24),default='active')
class FeedIssue(Base):
    __tablename__='feed_issues'
    __table_args__=(CheckConstraint('kg>0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    care_id:Mapped[int]=mapped_column(ForeignKey('care_actions.id'),unique=True)
    lot_id:Mapped[int]=mapped_column(ForeignKey('feed_lots.id'))
    kg:Mapped[float]=mapped_column(Float)
    state:Mapped[str]=mapped_column(String(24),default='issued')
    issued_by:Mapped[str]=mapped_column(String(120))
    issued_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
    returned_by:Mapped[str]=mapped_column(String(120),default='')
    return_reason:Mapped[str]=mapped_column(String(300),default='')
class QueenObservation(Base):
    __tablename__='queen_observations'
    id:Mapped[int]=mapped_column(primary_key=True)
    care_id:Mapped[int]=mapped_column(ForeignKey('care_actions.id'),unique=True)
    queen_code:Mapped[str]=mapped_column(String(50),unique=True)
    installed_on:Mapped[date]=mapped_column(Date)
    eggs_seen:Mapped[bool]=mapped_column(Boolean)
    accepted:Mapped[bool]=mapped_column(Boolean)
    note:Mapped[str]=mapped_column(String(300))
    state:Mapped[str]=mapped_column(String(24),default='observing')
    confirmed_by:Mapped[str]=mapped_column(String(120),default='')
