from typing import Dict, List

from backend.common.components.storage.backend import StorageBackend
from backend.common.components.storage.memory import MemoryStorageBackend
from backend.common.components.util import NetworkEntry
from backend.common.layers.routing.routing_layer import node_handler
from backend.implementation.keyinfra.keyinfra import KeyInfraNode
from backend.implementation.state.monitoring import CapitalState, RegionState
from backend.implementation.topology import build_cluster_topology


class CapitalNode(KeyInfraNode):
    def __init__(
        self,
        capital_name: str,
        entry: NetworkEntry,
        peers: List[NetworkEntry],
        backend: StorageBackend = MemoryStorageBackend()
    ):
        self.capital_name = capital_name
        super().__init__(entry, peers, [
            ("region.update", self.region_update),
            ("query.capital", self.query_capital),
        ], backend)

        self.ready_to_handle()

    def region_update(self, body: dict):
        update = RegionState.model_validate(body)

        self.get_state().regions[update.name] = update
        self.replication_plugin.commit(self.get_state())

        self._print_digest("capital")

    def query_capital(self, body: dict, source: str):
        print(f"BODY: {body}")
        return self.get_state().model_dump()

    def _ensure_cluster_connection(self, target: str):
        if target == self.get_network_name():
            return

        if self.has_connection(target):
            return

        topo = build_cluster_topology()
        info = topo.get(target)
        if info is None:
            return

        try:
            self._try_connect(info.to_network_entry())
        except Exception:
            pass

    def _safe_query_node_status(self, target: str) -> dict:
        topo = build_cluster_topology()
        info = topo[target]

        try:
            if target == self.get_network_name():
                result = self.handle_query_node_status({})
            else:
                self._ensure_cluster_connection(target)
                result = self.send_message(target, "query.node_status", {}, timeout=1.0)

            if "uri" not in result:
                result["uri"] = info.uri
            return result

        except Exception:
            return {
                "id": target,
                "kind": info.kind,
                "logical_name": info.logical_name,
                "uri": info.uri,
                "status": "down",
                "is_leader": False,
                "leader_replica": None,
                "version": None,
                "last_seen_unix": None,
                "last_seen": None,
                "infra_type": info.infra_type,
                "resource_value": None,
            }

    def query_cluster(self, body: dict, source: str):
        topo = build_cluster_topology()

        statuses: Dict[str, dict] = {}
        for node_name in topo.keys():
            statuses[node_name] = self._safe_query_node_status(node_name)

        capitals: Dict[str, List[dict]] = {}
        regions: Dict[str, List[dict]] = {}
        infrastructure: List[dict] = []

        for _, status in statuses.items():
            kind = status["kind"]
            logical_name = status["logical_name"]

            if kind == "capital":
                capitals.setdefault(logical_name, []).append(status)
            elif kind == "region":
                regions.setdefault(logical_name, []).append(status)
            elif kind == "infra":
                infrastructure.append(status)

        for bucket in capitals.values():
            bucket.sort(key=lambda x: x["id"])

        for bucket in regions.values():
            bucket.sort(key=lambda x: x["id"])

        infrastructure.sort(key=lambda x: x["id"])

        capital_leader_replica = None
        for bucket in capitals.values():
            leader = next((x["id"] for x in bucket if x.get("is_leader")), None)
            if leader is not None:
                capital_leader_replica = leader
                break

        return {
            "capital_namespace": self.capital_name,
            "capital_leader_replica": capital_leader_replica,
            "capitals": capitals,
            "regions": regions,
            "infrastructure": infrastructure,
        }

    @node_handler(name="query.cluster")
    def handle_query_cluster(self, body: dict, source: str):
        return self.query_cluster(body, source)

    def _default_state(self) -> CapitalState:
        return CapitalState(
            name=self.capital_name,
            regions={}
        )

    def _parse_state(self, data):
        return CapitalState.model_validate(data)