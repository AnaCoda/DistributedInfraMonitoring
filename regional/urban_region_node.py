import random

from .standard_region_node import StandardRegionNode

from infrastructure.powerplant import powerplant
from infrastructure.hospital import hospital
from infrastructure.railroads import railroads
from infrastructure.fuel_depot import fuel_depot
from infrastructure.water_treatment_plant import water_treatment_plant

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
    