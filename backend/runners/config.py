
from typing import List, Literal, Union

from pydantic import BaseModel
from enum import Enum

class RunnerClass(str, Enum):
    CAPITAL = 'capital'
    REGION = 'region'

class CapitalSpecificConfig(BaseModel):
    capital_name: str
    peers: List[str]

class RegionSpecificConfig(BaseModel):
    region_name: str
    capitals: List[str]
    peers: List[str]
    
class CapitalRunnerConfig(BaseModel):
    name: str
    variant: Literal[RunnerClass.CAPITAL]
    uri: str
    capital: CapitalSpecificConfig
    
class RegionRunnerConfig(BaseModel):
    name: str
    variant: Literal[RunnerClass.REGION]
    uri: str
    region: RegionSpecificConfig

def parse_runner_config(data: dict) -> Union[CapitalRunnerConfig, RegionRunnerConfig]:
    if data['variant'] == 'capital':
        return CapitalRunnerConfig.model_validate(data)
    elif data['variant'] == 'region':
        return RegionRunnerConfig.model_validate(data)

RunnerConfig = Union[CapitalRunnerConfig, RegionRunnerConfig]