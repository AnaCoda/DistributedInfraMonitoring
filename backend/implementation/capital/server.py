import logging
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
            ("query.capital", self.query_capital)
        ], backend)

        self.ready_to_handle()

    def region_update(self, body: dict, source: str):
        logging.info(f'Received region.update from {source}')
        update = RegionState.model_validate(body)
        self.get_state().regions[update.name] = update
        self.replication_plugin.commit(self.get_state())
        self._print_digest("capital")

    def query_capital(self, body: dict, source: str):
        logging.info(f'Received query.capital from {source}')
        return self.get_state().model_dump()

    @node_handler(name="query.cluster")
    def handle_query_cluster(self, body: dict, source: str):
        return self.query_cluster(body, source)

    @node_handler(name="control.infra.set_state")
    def handle_control_infra_set_state_proxy(self, body: dict, source: str):
        target = body.get("target")
        value = body.get("value")

        if not target:
            raise RuntimeError("control.infra.set_state requires target")

        self._ensure_cluster_connection(target)
        return self.send_message(target, "control.infra.set_state", {"value": value}, timeout=1.5)

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

    def _safe_query_region_group(self, logical_name: str, replica_names: List[str]) -> dict:
        topo = build_cluster_topology()

        for replica_name in replica_names:
            try:
                self._ensure_cluster_connection(replica_name)
                body = self.send_message(replica_name, "query.region", {}, timeout=1.5)
                return {
                    "name": logical_name,
                    "leader_replica": body.get("leader_replica"),
                    "replicas": body.get("replicas", []),
                    "infrastructure": body.get("infrastructure", {}),
                    "status": "up",
                }
            except Exception:
                continue

        cached_region = self.get_state().regions.get(logical_name)
        cached_infra = {}

        if cached_region is not None:
            for site_name, site in cached_region.infrastructure.items():
                if hasattr(site, "model_dump"):
                    cached_infra[site_name] = site.model_dump(mode="json")
                elif isinstance(site, dict):
                    cached_infra[site_name] = site
                else:
                    cached_infra[site_name] = {
                        "name": site_name,
                        "resource_type": "Unknown",
                        "value": site,
                    }

        return {
            "name": logical_name,
            "leader_replica": None,
            "replicas": [
                {
                    "id": replica_name,
                    "kind": "region",
                    "logical_name": logical_name,
                    "uri": topo[replica_name].uri,
                    "status": "down",
                    "is_leader": False,
                    "leader_replica": None,
                    "version": None,
                    "last_seen_unix": None,
                    "last_seen": None,
                }
                for replica_name in replica_names
            ],
            "infrastructure": cached_infra,
            "status": "down",
        }

    def query_cluster(self, body: dict, source: str):
        topo = build_cluster_topology()

        capital_groups: Dict[str, List[str]] = {}
        region_groups: Dict[str, List[str]] = {}

        for node_name, info in topo.items():
            if info.kind == "capital":
                capital_groups.setdefault(info.logical_name, []).append(node_name)
            elif info.kind == "region":
                region_groups.setdefault(info.logical_name, []).append(node_name)

        capitals: Dict[str, List[dict]] = {}
        for logical_name, replica_names in capital_groups.items():
            bucket = [self._safe_query_node_status(name) for name in replica_names]
            bucket.sort(key=lambda x: x["id"])
            capitals[logical_name] = bucket

        regions: Dict[str, dict] = {}
        infrastructure: List[dict] = []

        for logical_name, replica_names in region_groups.items():
            region_body = self._safe_query_region_group(logical_name, replica_names)
            regions[logical_name] = region_body

            for site_name, site in region_body.get("infrastructure", {}).items():
                if isinstance(site, dict):
                    site_name_out = site.get("name", site_name)
                    infra_type = site.get("resource_type")
                    resource_value = site.get("value", site.get("resource_value"))
                else:
                    site_name_out = site_name
                    infra_type = "Unknown"
                    resource_value = site

                infrastructure.append({
                    "id": site_name_out,
                    "kind": "infra",
                    "logical_name": logical_name,
                    "infra_type": infra_type,
                    "status": "up" if region_body.get("status") == "up" else "down",
                    "resource_value": resource_value,
                })

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

    def _default_state(self) -> CapitalState:
        return CapitalState(
            name=self.capital_name,
            regions={}
        )

    def _parse_state(self, data):
        return CapitalState.model_validate(data)