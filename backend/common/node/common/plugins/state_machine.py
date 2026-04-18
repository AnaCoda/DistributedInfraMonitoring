from typing import List, Optional, Any, Dict
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass

@dataclass
class StateMachineMessage:
    op: Enum
    source: str
    target: Enum | str
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

class BaseStateMachine(StateMachine):

    def __init__(self, name: str, init_state: Enum):
        super().__init__()
        self.__name = name
        self.__state = init_state
        self.__outbox = []

    def get_name(self) -> str:
        return self.__name

    def modify_outbound(self, msg: StateMachineMessage):
        msg.source = self.get_name()

    @abstractmethod
    def _on_poll(self):
        pass

    def _enqueue(self, message: StateMachineMessage):
        self.__outbox.append(message)

    def poll(self):
        self._on_poll()
        out = self.__outbox
        self.__outbox = []
        for o in out:
            self.modify_outbound(o)
        return out
        # return self.__outbox
        # return super().poll()

    def get_state(self):
        return self.__state

    def _set_state(self, state):
        self.__state = state
        # return super()._set_state(state
        # return super().get_state()