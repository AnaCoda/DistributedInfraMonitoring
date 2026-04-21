from typing import List
from threading import Lock
from random import randint
import logging
import time

from colorama import Fore

from ...common.raw import RawNode, node_handler
from ...common.components.util import NetworkEntry
from ..state.monitoring import InfrastructureState

LOGGER = logging.getLogger("node::infra")


class InfrastructureNode(RawNode):
    def __init__(
        self,
        entry: NetworkEntry,
        regions: List[NetworkEntry]
    ):
        super().__init__(entry.name, address=entry.address.to_tuple())

        self.regions = regions
        self.resource_value = 0
        self._logical_name = entry.name
        self._forced_value = None

        self.__region_notify_lock = Lock()
        self.__state_lock = Lock()
        self.__state = InfrastructureState(
            name=self.get_network_name(),
            resource_type=self.get_resource_type(),
            value=self.generate_value()
        )

        self.__notified_region = False
        self.ready_to_handle()

    def get_resource_type(self):
        raise NotImplementedError

    def update_value(self):
        with self.__state_lock:
            if self._forced_value is not None:
                self.__state.value = self._forced_value
            else:
                self.__state.value = self.generate_value()
        with self.__region_notify_lock:
            self.__notified_region = False

    def generate_value(self):
        return randint(0, 100)

    @node_handler(name="control.infra.set_state")
    def handle_control_infra_set_state(self, body: dict):
        value = body.get("value")
        if value is None:
            raise RuntimeError("control.infra.set_state requires 'value'")

        try:
            value = int(value)
        except Exception as exc:
            raise RuntimeError("value must be an integer") from exc

        self._forced_value = value
        with self.__state_lock:
            self.__state.value = value
        with self.__region_notify_lock:
            self.__notified_region = False

        return {
            "status": "success",
            "id": self.get_network_name(),
            "resource_value": value,
        }

    @node_handler(name="query.node_status")
    def handle_query_node_status(self, body: dict):
        now = time.time()

        with self.__state_lock:
            state = self.__state.model_dump(mode="json")

        return {
            "id": self.get_network_name(),
            "kind": "infra",
            "logical_name": self._logical_name,
            "infra_type": self.get_resource_type(),
            "status": "up",
            "resource_value": state["value"],
            "last_seen_unix": now,
            "last_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        }

    def __send_update_target(self, target: str):
        print(
            f'{Fore.YELLOW}[{self.get_network_name()}] '
            f'Pushing update of infrastructure to the regional node. '
            f'Current state: {self.__state.model_dump()}{Fore.RESET}'
        )
        with self.__state_lock:
            current_state = self.__state.model_dump()

        self.send_message_no_wait(target, 'infra.update', current_state)

        with self.__region_notify_lock:
            self.__notified_region = True

        print(
            f'{Fore.GREEN}[{self.get_network_name()}] '
            f'Succesfully notified the regional nodes of a change.'
        )

    @node_handler(name='infra.random')
    def handle_infra_random(self, body: dict):
        if self._forced_value is not None:
            return {"status": "ignored", "reason": "forced value active"}
        self.update_value()

    @node_handler(internal_ms=4000)
    def handle_update(self):
        self.update_value()

    @node_handler(internal_ms=200)
    def handle_tick(self):
        for region in self.regions:
            if not self.has_connection(region.name):
                self._try_connect(region)

        with self.__region_notify_lock:
            flag = not self.__notified_region

        if flag:
            for region in self.regions:
                try:
                    LOGGER.info(f'Trying to notify {region.name}')
                    self.__send_update_target(region.name)
                    LOGGER.info(f'Succesfully notified {region.name}')
                    break
                except Exception as e:
                    LOGGER.error(e)