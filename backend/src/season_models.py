from datetime import date,datetime
from sqlalchemy import String,Float,ForeignKey,JSON,CheckConstraint,Date,DateTime,func
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class ApiaryMove(Base):
    __tablename__='apiary_moves'
    id:Mapped[int]=mapped_column(primary_key=True)
    hive_id:Mapped[int]=mapped_column(ForeignKey('hives.id'))
    destination:Mapped[str]=mapped_column(String(50))
    move_date:Mapped[date]=mapped_column(Date)
    health_note:Mapped[str]=mapped_column(String(400))
    origin_snapshot:Mapped[dict]=mapped_column(JSON)
    state:Mapped[str]=mapped_column(String(24),default='requested')
    approved_by:Mapped[str]=mapped_column(String(120),default='')
    moved_by:Mapped[str]=mapped_column(String(120),default='')
class InsulationLot(Base):
    __tablename__='insulation_lots'
    __table_args__=(CheckConstraint('available_units>=0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(50),unique=True)
    available_units:Mapped[int]=mapped_column()
    state:Mapped[str]=mapped_column(String(24),default='active')
class InsulationInstall(Base):
    __tablename__='insulation_installs'
    __table_args__=(CheckConstraint('units>0 AND returned_units>=0 AND returned_units<=units'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    hive_id:Mapped[int]=mapped_column(ForeignKey('hives.id'))
    lot_id:Mapped[int]=mapped_column(ForeignKey('insulation_lots.id'))
    units:Mapped[int]=mapped_column()
    ventilation_checked:Mapped[bool]=mapped_column()
    state:Mapped[str]=mapped_column(String(24),default='installed')
    installed_by:Mapped[str]=mapped_column(String(120))
    accepted_by:Mapped[str]=mapped_column(String(120),default='')
    returned_units:Mapped[int]=mapped_column(default=0)
    removed_by:Mapped[str]=mapped_column(String(120),default='')
class SpringReview(Base):
    __tablename__='spring_reviews'
    __table_args__=(CheckConstraint('opening_weight>0 AND frames>=0 AND frames<=20 AND mortality_pct>=0 AND mortality_pct<=100'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    hive_id:Mapped[int]=mapped_column(ForeignKey('hives.id'),unique=True)
    install_id:Mapped[int]=mapped_column(ForeignKey('insulation_installs.id'))
    opening_weight:Mapped[float]=mapped_column(Float)
    frames:Mapped[int]=mapped_column()
    queen_seen:Mapped[bool]=mapped_column()
    mortality_pct:Mapped[float]=mapped_column(Float)
    winter_snapshot:Mapped[dict]=mapped_column(JSON)
    rescue_after_care_id:Mapped[int]=mapped_column()
    rescue_care_id:Mapped[int|None]=mapped_column(ForeignKey('care_actions.id'),nullable=True,unique=True)
    state:Mapped[str]=mapped_column(String(24))
    resolution:Mapped[str]=mapped_column(String(400),default='')
    passed_by:Mapped[str]=mapped_column(String(120),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
