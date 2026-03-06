import time
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from ..shared.node import NodeBase, node_handler, NodeConnectionType


class RegionalNode(NodeBase, ABC):
    """
    TCP-based regional node.
    - Listens on its own address (required by NodeBase)
    - Connects outbound to Capital
    - Periodically sends infra heartbeat via TCP RPC
    """

    def __init__(
        self,
        region_name: str,
        address: Tuple[str, int],
        capital_address: Tuple[str, int],
        interval_ms: int = 2000,
    ):
        super().__init__(network_name=region_name, address=address)

        if region_name.strip().lower() == "capital":
            raise ValueError("Region name cannot be 'Capital' (reserved).")

        self.region_name = region_name
        self.capital_address = capital_address
        self.interval_ms = interval_ms

        self.sites = self.build_sites()

        # Establish outbound connection to capital (target registered by capital's network_name)
        self.connect(capital_address)

    @abstractmethod
    def build_sites(self) -> List[Any]:
        raise NotImplementedError

    @abstractmethod
    def aggregate_state(self) -> Dict[str, Any]:
        raise NotImplementedError

    def simulate_tick(self) -> None:
        for s in self.sites:
            t = getattr(s, "resource_type", "")
            if t == "Powerplant":
                s.resource_value = random.choices(["stable","unstable","down"], [0.75,0.20,0.05])[0]
            elif t == "Railroad":
                s.resource_value = random.choices(["operational","degraded","down"], [0.75,0.20,0.05])[0]
            elif t in ["Hospital", "Fuel Depot", "Water Treatment Plant"]:
                cur = int(s.resource_value)
                delta = random.randint(-3, 2)  # slower decay so demo doesn't instantly hit 0
                s.resource_value = max(0, min(100, cur + delta))

    def sites_snapshot(self) -> List[Dict[str, Any]]:
        snap = []
        for s in self.sites:
            if hasattr(s, "report") and callable(getattr(s, "report")):
                snap.append(s.to_dict())  # IMPORTANT: to_dict(), not report()
            else:
                snap.append({
                    "name": getattr(s, "name", "unknown"),
                    "region_name": getattr(s, "region_name", self.region_name),
                    "resource_type": getattr(s, "resource_type", "unknown"),
                    "resource_value": getattr(s, "resource_value", None),
                })
        return snap

    def heartbeat_payload(self) -> Dict[str, Any]:
        return {
            "name": self.region_name,
            "state": self.aggregate_state(),
            "meta": {
                "timestamp": time.time(),
                "region_type": self.__class__.__name__,
                "sites": self.sites_snapshot(),
            },
        }

    def infra_addr(self, site_id: str, host="127.0.0.1", base_port=32000, span=4000):
        key = f"{self.region_name}:{site_id}"
        h = 0
        for ch in key:
            h = (h * 31 + ord(ch)) % span
        return (host, base_port + h)

    @node_handler(name="region.ping")
    def ping(self, message: dict):
        return {"pong": True, "region": self.network_name}

    @node_handler(name="api.report")
    def handle_report(self, msg: dict):
        """
        msg: {"name","region_name","resource_type","resource_value"}
        """
        print(f"[{self.region_name}] got report: {msg}")
        # simplest: update the matching site object in self.sites
        site_name = msg.get("name")
        for s in self.sites:
            if getattr(s, "name", None) == site_name:
                s.resource_value = msg.get("resource_value")
                break
        return {"status": "ok"}

    @node_handler(on_connect=NodeConnectionType.OUTBOUND)
    def on_outbound_connect(self, name: str):
        print(f"[{self.region_name}] outbound connected to {name}")

    @node_handler(on_disconnect=NodeConnectionType.OUTBOUND)
    def on_outbound_disconnect(self, name: str):
        print(f"[{self.region_name}] outbound disconnected from {name}")


    def tick_and_send(self) -> None:
        self.simulate_tick()
        state = self.aggregate_state()

        self.send_message(
            target="Capital",
            method="api.update_state",
            body={
                "name": self.region_name,
                "state": {
                    "state": state,
                    "meta": {
                        "region_type": self.__class__.__name__,
                        "sites": self.sites_snapshot(),
                    },
                },
            }
        )