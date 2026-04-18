from typing import List, Optional, Any
from abc import ABC, abstractmethod


class StateMachine(ABC):


    @abstractmethod
    def poll(self) -> List[Any]:
        pass

    @abstractmethod
    def receive(self, packet: Optional[Any]) -> None:
        pass