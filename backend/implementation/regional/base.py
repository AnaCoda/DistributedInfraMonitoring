from typing import Dict, List

from backend.common.components.storage.backend import StorageBackend
from backend.common.components.storage.memory import MemoryStorageBackend
from backend.common.components.util import NetworkEntry
from backend.common.layers.routing.routing_layer import node_handler
from backend.implementation.keyinfra.keyinfra import KeyInfraNode
from backend.implementation.state.monitoring import InfrastructureState, RegionState


class RegionalNode(KeyInfraNode):
    def __init__(
        self,
        region_name: str,
        entry: NetworkEntry,
        capital_addresses: List[NetworkEntry],
        peers: List[NetworkEntry],
        backend: StorageBackend = MemoryStorageBackend()
    ):
        self.region_name = region_name

        super().__init__(entry, peers, [
            ("infra.update", self.handle_infra_update),
        ], backend)

        self.capitals = capital_addresses
        self.__dirty = True

        self.ready_to_handle()

    def _default_state(self) -> RegionState:
        return RegionState(
            name=self.region_name,
            infrastructure={}
        )

    def _parse_state(self, data: Dict) -> RegionState:
        return RegionState.model_validate(data)

    def handle_infra_update(self, body: dict):
        infra_state = InfrastructureState.model_validate(body)
        self.get_state().infrastructure[infra_state.name] = infra_state
        self.replication_plugin.commit(self.get_state())

        self._print_digest("region")
        self.__dirty = True

    @node_handler(name="query.region")
    def handle_query_region(self, body: dict, source: str):
        replicas = []

        # self first
        replicas.append(self.handle_query_node_status({}))

        # peers best-effort
        for peer in self.peers:
            try:
                if not self.has_connection(peer.name):
                    self._try_connect(peer)
                status = self.send_message(peer.name, "query.node_status", {}, timeout=1.0)
                replicas.append(status)
            except Exception:
                replicas.append({
                    "id": peer.name,
                    "kind": "region",
                    "logical_name": self.region_name,
                    "status": "down",
                    "is_leader": False,
                    "leader_replica": None,
                    "version": None,
                    "last_seen_unix": None,
                    "last_seen": None,
                })

        replicas.sort(key=lambda x: x["id"])
        leader_replica = next((r["id"] for r in replicas if r.get("is_leader")), None)

        infrastructure = {}
        for site_name, site in self.get_state().infrastructure.items():
            if hasattr(site, "model_dump"):
                infrastructure[site_name] = site.model_dump(mode="json")
            elif isinstance(site, dict):
                infrastructure[site_name] = site
            else:
                infrastructure[site_name] = {
                    "name": site_name,
                    "resource_type": "Unknown",
                    "value": site,
                }

        return {
            "name": self.region_name,
            "leader_replica": leader_replica,
            "replicas": replicas,
            "infrastructure": infrastructure,
        }

    def __send_update_target(self, target: str):
        try:
            current_state: dict = self.get_state().model_dump()
            self.send_message(target, "region.update", current_state)
            self.__dirty = False
        except Exception as e:
            print(f"[{self.get_network_name()}] Failed to send region update to {target}: {e}")

    @node_handler(internal_ms=500)
    def periodical(self):
        for region in self.capitals:
            if not self.has_connection(region.name):
                self._try_connect(region)

        if self.__dirty:
            for region in self.capitals:
                self.__send_update_target(region.name)
                break