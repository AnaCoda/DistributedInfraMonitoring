from __future__ import annotations
from typing import Dict, Optional
from pydantic import BaseModel

from backend.common.components.plugins.leader_elec.bully_state_machine import HBMsgState
from backend.common.components.util import NetworkEntry



class CapitalState(BaseModel):
    name: str
    regions: dict[str, RegionState]

class RegionState(BaseModel):
    name: str
    infrastructure: dict[str, InfrastructureState]

class InfrastructureState(BaseModel):
    name: str
    resource_type: str
    value: int | str




class HeartBeatState(BaseModel):
    heartbeat_state: HBMsgState
    last_heartbeat: float

class ElectionState(BaseModel):
    name: str
    leader: Optional[str]
    version: int
    heartbeat: Dict[str, HeartBeatState]