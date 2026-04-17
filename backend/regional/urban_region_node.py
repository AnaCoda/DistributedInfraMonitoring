import random

from .standard_region_node import StandardRegionNode

from ..infrastructure.powerplant import Powerplant
from ..infrastructure.hospital import Hospital
from ..infrastructure.railroads import Railroad
from ..infrastructure.fuel_depot import FuelDepot
from ..infrastructure.water_treatment_plant import WaterTreatmentPlant

class UrbanRegionNode(StandardRegionNode):
    """
    Urban region: more hospitals + faster recovery in medical capacity,
    but transport degrades more under stress (demo dynamics).
    """

    def build_sites(self):
        rn = self.region_name
        region_addr = self.address 

        return [
            Powerplant("pp-1", rn, self.infra_addr("pp-1"), region_addr),

            Hospital("h-1", rn, self.infra_addr("h-1"), region_addr),
            Hospital("h-2", rn, self.infra_addr("h-2"), region_addr),

            Railroad("rr-1", rn, self.infra_addr("rr-1"), region_addr),
            Railroad("rr-2", rn, self.infra_addr("rr-2"), region_addr),

            WaterTreatmentPlant("wtp-1", rn, self.infra_addr("wtp-1"), region_addr),
            FuelDepot("fd-1", rn, self.infra_addr("fd-1"), region_addr),
        ]

    def simulate_tick(self) -> None:
        super().simulate_tick()

        # Urban: medical recovers slightly more often
        for s in self.sites:
            if hasattr(s, "is_outage_active") and callable(getattr(s, "is_outage_active")) and s.is_outage_active():
                continue
            if s.resource_type == "Hospital":
                try:
                    cur = int(s.resource_value)
                except (TypeError, ValueError):
                    cur = 100
                s.resource_value = max(0, min(100, cur + random.randint(-4, 8)))

        # Urban: transport can be more brittle (congestion)
        for s in self.sites:
            if hasattr(s, "is_outage_active") and callable(getattr(s, "is_outage_active")) and s.is_outage_active():
                continue
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
    