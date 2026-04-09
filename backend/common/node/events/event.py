from dataclasses import dataclass
from typing import Callable
from enum import Enum
from abc import ABC, abstractmethod

from ..template import NodeTemplate

class NodeEvent(Enum):
    """
    The node event type.
    """
    ON_CONNECT = 0
    ON_DISCONNECT = 1

@dataclass
class Event(ABC):
    
    @abstractmethod
    def invoke(self, node: NodeTemplate, *args, **kwargs) -> any:
        pass
