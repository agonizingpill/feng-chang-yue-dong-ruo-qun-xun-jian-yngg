from datetime import date
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
class Input(BaseModel):
    model_config=ConfigDict(allow_inf_nan=False)
class MoveInput(Input):
    hive_id:int
    destination:str=Field(min_length=2,max_length=50)
    move_date:date
    health_note:str=Field(min_length=5,max_length=400)
class InsulationInput(Input):
    code:str=Field(min_length=2,max_length=50)
    available_units:int=Field(ge=1,le=10000)
class LotState(Input):
    state:Literal['active','quarantine']
class InstallInput(Input):
    hive_id:int
    lot_id:int
    units:int=Field(ge=1,le=100)
    ventilation_checked:bool
class VentilationInput(Input):
    ventilation_checked:bool
class RemoveInput(Input):
    reusable_units:int=Field(ge=0,le=100)
class SpringInput(Input):
    hive_id:int
    opening_weight:float=Field(gt=0,le=100)
    frames:int=Field(ge=0,le=20)
    queen_seen:bool
    mortality_pct:float=Field(ge=0,le=100)
class PassInput(Input):
    rescue_care_id:int|None=None
    resolution:str=Field(min_length=5,max_length=400)
