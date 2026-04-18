from typing import List, Optional, Any, Dict
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass

@dataclass
class StateMachineMessage:
    op: Enum
    body: Dict


class StateMachine(ABC):

    @abstractmethod
    def get_state(self) -> Enum:
        pass

    @abstractmethod
    def _set_state(self, state: Enum):
        pass

    @abstractmethod
    def poll(self) -> List[StateMachineMessage]:
        pass

    @abstractmethod
    def receive(self, packet: Optional[StateMachineMessage]) -> None:
        pass