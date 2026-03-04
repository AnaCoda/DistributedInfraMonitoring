# regional/node.py
import argparse
import time
import random
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

import requests

from infrastructure.powerplant import powerplant
from infrastructure.hospital import hospital
from infrastructure.railroads import railroads
from infrastructure.fuel_depot import fuel_depot
from infrastructure.water_treatment_plant import water_treatment_plant

DEFAULT_CAPITAL = "http://localhost:5000"


class RegionalNode(ABC):
    """
    A regional node is a separate process that:
      - owns local infrastructure sites
      - simulates and/or reads local site values
      - aggregates to a region summary
      - heartbeats to the capital server
    """

    def __init__(self, region_name: str, capital_url: str, interval_s: float = 2.0):
        if region_name.strip().lower() == "capital":
            raise ValueError("Region name cannot be 'Capital' (reserved).")

        self.region_name = region_name
        self.capital_url = capital_url.rstrip("/")
        self.interval_s = interval_s

        self.sites = self.build_sites()

        # backoff for network failures
        self._backoff_s = 1.0

    @abstractmethod
    def build_sites(self) -> List[Any]:
        """Return a list of infrastructure site objects owned by this region."""
        raise NotImplementedError

    @abstractmethod
    def aggregate_state(self) -> Dict[str, Any]:
        """
        Produce the summarized state_infrastructure dict expected by the capital.
        Must return keys: power, medical_capacity, transport, water_capacity, fuel_storage
        """
        raise NotImplementedError

    def simulate_tick(self) -> None:
        """
        Default simulation: make plausible small changes.
        Region subclasses can override for different dynamics.
        """
        for s in self.sites:
            t = getattr(s, "resource_type", "")

            if t == "Powerplant":
                s.resource_value = random.choices(
                    ["stable", "unstable", "down"],
                    weights=[0.75, 0.20, 0.05],
                    k=1
                )[0]

            elif t == "Railroad":
                s.resource_value = random.choices(
                    ["operational", "degraded", "down"],
                    weights=[0.75, 0.20, 0.05],
                    k=1
                )[0]

            elif t in ["Hospital", "Fuel Depot", "Water Treatment Plant"]:
                cur = int(s.resource_value)
                delta = random.randint(-8, 4)  # drift downward more often
                s.resource_value = max(0, min(100, cur + delta))

    def sites_snapshot(self) -> List[Dict[str, Any]]:
        """Full details for debugging/UI/reporting."""
        snap = []
        for s in self.sites:
            # prefer report() if present
            if hasattr(s, "report") and callable(getattr(s, "report")):
                snap.append(s.to_dict())
            else:
                snap.append({
                    "name": getattr(s, "name", "unknown"),
                    "region_name": getattr(s, "region_name", self.region_name),
                    "resource_type": getattr(s, "resource_type", "unknown"),
                    "resource_value": getattr(s, "resource_value", None),
                })
        return snap

    def heartbeat_payload(self) -> Dict[str, Any]:
        now = time.time()
        return {
            "name": self.region_name,
            "state": self.aggregate_state(),
            "meta": {
                "timestamp": now,
                "region_type": self.__class__.__name__,
                "sites": self.sites_snapshot(),
            }
        }

    def send_heartbeat(self) -> None:
        payload = self.heartbeat_payload()
        r = requests.post(f"{self.capital_url}/api/update_state", json=payload, timeout=3)
        r.raise_for_status()

    def run_forever(self) -> None:
        print(f"[regional] {self.region_name} ({self.__class__.__name__}) -> {self.capital_url} every {self.interval_s}s")
        while True:
            self.simulate_tick()

            try:
                self.send_heartbeat()
                self._backoff_s = 1.0
                time.sleep(self.interval_s)

            except Exception as e:
                print(f"[regional:{self.region_name}] heartbeat failed: {e} (retry in {self._backoff_s:.1f}s)")
                time.sleep(self._backoff_s)
                self._backoff_s = min(self._backoff_s * 2.0, 30.0)


# ---- Concrete region types ----

class StandardRegionNode(RegionalNode):
    """
    Baseline region: one of each core infrastructure site.
    """

    def build_sites(self):
        rn = self.region_name
        return [
            powerplant("pp-1", rn),
            hospital("h-1", rn),
            railroads("rr-1", rn),
            water_treatment_plant("wtp-1", rn),
            fuel_depot("fd-1", rn),
        ]

    def aggregate_state(self):
        power = "stable"
        transport = "operational"
        medical = 100
        water = 100
        fuel = 100

        for s in self.sites:
            if s.resource_type == "Powerplant":
                power = s.resource_value
            elif s.resource_type == "Railroad":
                transport = s.resource_value
            elif s.resource_type == "Hospital":
                medical = int(s.resource_value)
            elif s.resource_type == "Water Treatment Plant":
                water = int(s.resource_value)
            elif s.resource_type == "Fuel Depot":
                fuel = int(s.resource_value)

        return {
            "power": power,
            "medical_capacity": medical,
            "transport": transport,
            "water_capacity": water,
            "fuel_storage": fuel,
        }


class UrbanRegionNode(StandardRegionNode):
    """
    Urban region: more hospitals + faster recovery in medical capacity,
    but transport degrades more under stress (demo dynamics).
    """

    def build_sites(self):
        rn = self.region_name
        return [
            powerplant("pp-1", rn),
            hospital("h-1", rn),
            hospital("h-2", rn),
            railroads("rr-1", rn),
            railroads("rr-2", rn),
            water_treatment_plant("wtp-1", rn),
            fuel_depot("fd-1", rn),
        ]

    def simulate_tick(self):
        # Start with base simulation
        super().simulate_tick()

        # Urban: medical recovers slightly more often
        for s in self.sites:
            if s.resource_type == "Hospital":
                cur = int(s.resource_value)
                s.resource_value = max(0, min(100, cur + random.randint(-4, 8)))

        # Urban: transport can be more brittle (congestion)
        for s in self.sites:
            if s.resource_type == "Railroad":
                s.resource_value = random.choices(
                    ["operational", "degraded", "down"],
                    weights=[0.60, 0.30, 0.10],
                    k=1
                )[0]

    def aggregate_state(self):
        # Aggregate hospitals by average (urban has multiple)
        power = "stable"
        transport_vals = []
        hospitals = []
        water = 100
        fuel = 100

        for s in self.sites:
            if s.resource_type == "Powerplant":
                power = s.resource_value
            elif s.resource_type == "Railroad":
                transport_vals.append(s.resource_value)
            elif s.resource_type == "Hospital":
                hospitals.append(int(s.resource_value))
            elif s.resource_type == "Water Treatment Plant":
                water = int(s.resource_value)
            elif s.resource_type == "Fuel Depot":
                fuel = int(s.resource_value)

        # transport worst-case (if any down => down)
        if "down" in transport_vals:
            transport = "down"
        elif "degraded" in transport_vals:
            transport = "degraded"
        else:
            transport = "operational"

        medical = int(sum(hospitals) / len(hospitals)) if hospitals else 100

        return {
            "power": power,
            "medical_capacity": medical,
            "transport": transport,
            "water_capacity": water,
            "fuel_storage": fuel,
        }


NODE_TYPES = {
    "standard": StandardRegionNode,
    "urban": UrbanRegionNode,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Unique region name, e.g. Alberta")
    parser.add_argument("--type", default="standard", choices=NODE_TYPES.keys(), help="Region type")
    parser.add_argument("--capital", default=DEFAULT_CAPITAL, help="Capital base URL, e.g. http://localhost:5000")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between heartbeats")
    args = parser.parse_args()

    node_cls = NODE_TYPES[args.type]
    node = node_cls(region_name=args.name, capital_url=args.capital, interval_s=args.interval)
    node.run_forever()


if __name__ == "__main__":
    main()