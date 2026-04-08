from dataclasses import dataclass
from typing import Callable
from enum import Enum

class NodeEvent(Enum):
    """
    The node event type.
    """
    ON_CONNECT = 0
    ON_DISCONNECT = 1

@dataclass
class Event:
    pass
