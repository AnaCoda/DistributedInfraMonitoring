from __future__ import annotations
from pydantic import BaseModel



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

