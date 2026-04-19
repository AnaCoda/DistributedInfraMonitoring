from __future__ import annotations
from typing import Optional, Any, Dict
from dataclasses import dataclass
from pydantic import BaseModel


# @dataclass
class StateInfrastructure(BaseModel):
    power: str = 'stable'
    medical_capacity: int = 100
    transport: str = 'operational'
    water_capacity: int = 100
    fuel_storage: int = 100

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

@dataclass
class CapitalState:
    heartbeat: dict
    state: Dict[str, StateInfrastructure]