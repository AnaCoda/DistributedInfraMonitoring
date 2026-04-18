from __future__ import annotations
from ...template import NodeTemplate

from typing import Callable, Any
import inspect
from ...events.event import NodeEvent, Event
from ...events.connect import NodeConnectionType, EventOnConnectRegistry, EventOnDisconnectRegistry
from dataclasses import dataclass
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from ....sync.signal import HoldSignal
import time





class FunctionalLayer(NodeTemplate):

    def __init__(self):
        super().__init__()
        self.__shutdown_evt = Event()
        # self.__shutdown_flag = False

    def is_shutting_down(self) -> bool:
        return self.__shutdown_evt.is_set()
    
    def shutdown(self):
        self.__shutdown_evt.set()
        # self.__shutdown_flag = True
        super().shutdown()