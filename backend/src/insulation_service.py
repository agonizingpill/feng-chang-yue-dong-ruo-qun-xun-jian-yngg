from sqlalchemy import select
from fastapi import HTTPException
from .models import Hive
from .season_models import InsulationLot,InsulationInstall
from .yard_service import require,audit

def install(db,b,u):
    h=require(db,Hive,b.hive_id,True)
    if db.scalar(select(InsulationInstall.id).where(InsulationInstall.hive_id==h.id,InsulationInstall.state.in_(['installed','accepted']))):raise HTTPException(409,'该箱已有活跃保温安装')
    lot=require(db,InsulationLot,b.lot_id,True)
    if lot.state!='active' or lot.available_units<b.units:raise HTTPException(409,'保温物料隔离或库存不足')
    lot.available_units-=b.units;row=InsulationInstall(**b.model_dump(),installed_by=u.email);db.add(row);audit(db,u,f'安装保温 {h.code} 扣{b.units}件');db.commit();return row

def change(db,key,b,u,action):
    ref=require(db,InsulationInstall,key);h=require(db,Hive,ref.hive_id,True);row=require(db,InsulationInstall,key,True)
    if action=='ventilation':
        if row.state!='installed':raise HTTPException(409,'验收后通风记录冻结')
        row.ventilation_checked=b.ventilation_checked
    elif action=='accept':
        if row.state!='installed' or not row.ventilation_checked:raise HTTPException(409,'须安装且通风已核查，不能重复验收')
        row.state='accepted';row.accepted_by=u.email
    else:
        if row.state not in ['installed','accepted']:raise HTTPException(409,'保温物料已拆除归还，不能重复')
        if b.reusable_units>row.units:raise HTTPException(409,'归还可复用件数不得超原安装量')
        lot=require(db,InsulationLot,row.lot_id,True);lot.available_units+=b.reusable_units;row.returned_units=b.reusable_units;row.removed_by=u.email;row.state='removed'
    audit(db,u,f'保温安装{key} {action}');db.commit();return row
