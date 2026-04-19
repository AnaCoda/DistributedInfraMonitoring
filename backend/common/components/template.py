
from typing import Optional, Callable
from abc import ABC, abstractmethod

from backend.common.components.util import NetworkAddress

class NodeTemplate(ABC):


    @abstractmethod
    def _try_connect(self, address: NetworkAddress):
        pass

    @abstractmethod
    def disconnect(self, name: str):
        pass

    @abstractmethod
    def _register_route(self, route: str, functor: Callable[..., any]):
        pass

    @abstractmethod
    def wait_ready(self):
        pass

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
