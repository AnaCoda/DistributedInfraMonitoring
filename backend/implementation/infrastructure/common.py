# from ..shared.node import NodeBase, node_handler
# from debugpy import connect



from random import randint

from backend.common.components.events.connect import NodeConnectionType

from ...common.raw import RawNode, node_handler
from abc import abstractmethod

from typing import List

from threading import Lock

from ..state.monitoring import InfrastructureState
from ...common.components.util import NetworkEntry


class InfrastructureNode(RawNode):
    def __init__(
        self,
        network_name,
        regions: List[NetworkEntry]
    ):
        super().__init__(network_name, address=('0.0.0.0', 4000))

        self.regions = regions
        self.resource_value = 0

        self.__region_notify_lock = Lock()
        self.__state_lock = Lock()
        self.__state = InfrastructureState(
            name=self.get_network_name(),
            resource_type=self.get_resource_type(),
            value=self.generate_value()
        )

        self.__notified_region: bool = False

        self.ready_to_handle()

    @abstractmethod
    def get_resource_type(self):
        pass

    def update_value(self):
        with self.__state_lock:
            self.__state.value = self.generate_value()
        with self.__region_notify_lock:
            self.__notified_region = False

    def generate_value(self):
        return randint(0, 100)


    def __send_update_target(
        self,
        target: str
    ):
        with self.__state_lock:
            current_state: dict = self.__state.model_dump()

        
        self.send_message_no_wait(target, 'infra.update', current_state)
        with self.__region_notify_lock:
            self.__notified_region = True


    @node_handler(name='infra.random')
    def handle_infra_random(self, body: dict):
        self.update_value()
    
    
    @node_handler(internal_ms=200)
    def handle_tick(self):
        # Try to connect to the regions if we are
        # not already connected.
        for region in self.regions:
            if not self.has_connection(region.name):
                self._try_connect(region.address)
        
        with self.__region_notify_lock:
            # Check if we need to send any updates.
            flag = not self.__notified_region

        if flag:
            # Recall that we only need to send an
            # update to ONE of the nodes, not all of
            # them.
            for region in self.regions:
                if self.has_connection(region.name):
                    self.__send_update_target(region.name)
                    break
    