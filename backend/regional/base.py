# backend/regional/base.py
import time
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from shared.node import NodeBase, node_handler, NodeConnectionType


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
                s.resource_value = random.choices(
                    ["stable", "unstable", "down"], weights=[0.75, 0.20, 0.05], k=1
                )[0]
            elif t == "Railroad":
                s.resource_value = random.choices(
                    ["operational", "degraded", "down"], weights=[0.75, 0.20, 0.05], k=1
                )[0]
            elif t in ["Hospital", "Fuel Depot", "Water Treatment Plant"]:
                cur = int(s.resource_value)
                delta = random.randint(-8, 4)
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

    @node_handler(name="region.ping")
    def ping(self, message: dict):
        return {"pong": True, "region": self.network_name}

    @node_handler(on_connect=NodeConnectionType.OUTBOUND)
    def on_outbound_connect(self, name: str):
        print(f"[{self.region_name}] outbound connected to {name}")

    @node_handler(on_disconnect=NodeConnectionType.OUTBOUND)
    def on_outbound_disconnect(self, name: str):
        print(f"[{self.region_name}] outbound disconnected from {name}")

    # ---- Heartbeat loop ----
    # NOTE: node_handler(internal_ms=...) is static; we’ll set it in subclasses OR use a background thread.
    # For now we’ll NOT use the decorator here.
    def tick_and_send(self):
        self.simulate_tick()
        payload = self.heartbeat_payload()

        # Capital must have network_name="Capital"
        # and a route handler name="infra.heartbeat"
        self.send_message(target="Capital", method="infra.heartbeat", body=payload)