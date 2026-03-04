from .base import RegionalNode

from infrastructure.powerplant import powerplant
from infrastructure.hospital import hospital
from infrastructure.railroads import railroads
from infrastructure.fuel_depot import fuel_depot
from infrastructure.water_treatment_plant import water_treatment_plant

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
