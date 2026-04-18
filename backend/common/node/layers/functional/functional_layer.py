from __future__ import annotations
from ...common.template import NodeTemplate

from typing import Callable, Any
import inspect
from ...common.events.event import NodeEvent, Event
from ...common.events.connect import NodeConnectionType, EventOnConnectRegistry, EventOnDisconnectRegistry
from dataclasses import dataclass
from threading import Event
from concurrent.futures import ThreadPoolExecutor
import time





class FunctionalLayer(NodeTemplate):

    def __init__(self):
        super().__init__()
        self.__shutdown_evt = Event()
        self.__started_evt = Event()
        # self.__shutdown_flag = False

    def ready_to_handle(self):
        """
        This method should be invoked when we are ready to
        handle events.
        """
        self.__started_evt.set()
        # import colorama
        # print(f'{colorama.Fore.YELLOW} The node {self.get_network_name()} is ready. {colorama.Fore.RESET}')

    def wait_ready(self): 

        while not self.__started_evt.is_set():
            self.__started_evt.wait()

    def is_shutting_down(self) -> bool:
        return self.__shutdown_evt.is_set()
    
    def shutdown(self):
        self.__shutdown_evt.set()
        # self.__shutdown_flag = True
        super().shutdown()