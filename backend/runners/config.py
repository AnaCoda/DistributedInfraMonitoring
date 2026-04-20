
from typing import List, Literal, Union

from pydantic import BaseModel
from enum import Enum

class RunnerClass(str, Enum):
    CAPITAL = 'capital'

class CapitalSpecificConfig(BaseModel):
    capital_name: str
    peers: List[str]
    
class CapitalRunnerConfig(BaseModel):
    name: str
    variant: Literal[RunnerClass.CAPITAL]
    uri: str
    capital: CapitalSpecificConfig
    

RunnerConfig = Union[CapitalRunnerConfig]