from dataclasses import dataclass
from typing import Callable
from .event import Event
from enum import Enum
from ..template import NodeTemplate


class NodeConnectionType(Enum):
    """
    The connection type of the event, i.e., if it is an inbound or an outbound
    event.
    """
    INBOUND = 0
    OUTBOUND = 1


@dataclass
class EventOnConnectRegistry(Event):
    """
    Registers an event handler for the OnConnect event.
    There are two variants defined by method:
        INBOUND: We have received a connection.
        OUTBOUND: We have made a connection with an outbound
        client.
    """
    functor: Callable[..., None]
    # method: NodeConnectionType

    def invoke(self, node: NodeTemplate, *args, **kwargs):
        return self.functor(*args, **kwargs)


@dataclass
class EventOnDisconnectRegistry(Event):
    """
    Registers an event handler for the OnDisconnect event.
    There are two variants defined by method:
        INBOUND: We have received a connection.
        OUTBOUND: We have made a connection with an outbound
        client.
    """
    functor: Callable[..., None]
    method: NodeConnectionType

    def invoke(self, node: NodeTemplate, *args, **kwargs):
        return self.functor(*args, **kwargs)