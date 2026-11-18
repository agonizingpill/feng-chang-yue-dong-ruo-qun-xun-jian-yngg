from datetime import date
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict,field_validator
class Inputs(BaseModel):
    model_config=ConfigDict(allow_inf_nan=False)
class LotInput(Inputs):
    code:str=Field(min_length=1,max_length=50)
    received_kg:float=Field(gt=0,le=10000)
    expires_on:date
    @field_validator('code')
    @classmethod
    def code_required(cls,v):
        if not v.strip():raise ValueError('批号不能为空')
        return v.strip()
class LotState(Inputs):
    state:Literal['active','quarantine']
class IssueInput(Inputs):
    care_id:int
    lot_id:int
class CancelInput(Inputs):
    reason:str=Field(min_length=5,max_length=300)
    @field_validator('reason')
    @classmethod
    def reason_required(cls,v):
        if len(v.strip())<5:raise ValueError('取消依据至少5字')
        return v.strip()
class QueenInput(Inputs):
    care_id:int
    queen_code:str=Field(min_length=1,max_length=50)
    installed_on:date
    eggs_seen:bool
    accepted:bool
    note:str=Field(min_length=5,max_length=300)
    @field_validator('queen_code','note')
    @classmethod
    def required(cls,v):
        if not v.strip():raise ValueError('不能为空')
        return v.strip()
