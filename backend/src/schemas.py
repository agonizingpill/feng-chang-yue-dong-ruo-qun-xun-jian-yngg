from pydantic import BaseModel,Field
from .constants import CareKind
class Login(BaseModel):
    email:str
    password:str
class HiveInput(BaseModel):
    code:str=Field(min_length=1,max_length=30)
    site:str=Field(min_length=1,max_length=50)
    queen_present:bool
    colony_frames:int=Field(ge=0,le=20)
class VisitInput(BaseModel):
    code:str=Field(min_length=1,max_length=50)
    hive_id:int
    weight_kg:float=Field(gt=0,le=100)
    temperature:float=Field(ge=-10,le=50)
    activity:float=Field(ge=0,le=500)
    feed_left:float=Field(ge=0,le=20)
    queen_seen:bool
    colony_frames:int=Field(ge=0,le=20)
class CareInput(BaseModel):
    visit_id:int
    kind:CareKind
    feed_kg:float=Field(ge=0,le=10)
class ExecutionInput(BaseModel):
    queen_installed:bool=False
class FollowupInput(BaseModel):
    followup_weight:float=Field(gt=0,le=100)
    followup_queen:bool
    followup_frames:int=Field(ge=0,le=20)
