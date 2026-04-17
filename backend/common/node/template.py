
from typing import Optional
from abc import ABC, abstractmethod

class NodeTemplate(ABC):

    @abstractmethod
    def has_connection(self, target: Optional[str]) -> bool:
        pass

    @abstractmethod
    def shutdown(self):
        pass

    @abstractmethod
    def get_network_name(self) -> str:
        pass

    @abstractmethod
    def send_message_no_wait(
        self,
        target: str,
        method: str,
        body: dict
    ):
        pass

    @abstractmethod
    def send_message(
        self,
        target: str,
        method: str,
        body: dict,
        timeout: Optional[float] = 2.0
    ):
        pass
