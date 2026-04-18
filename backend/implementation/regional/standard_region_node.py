from .base import RegionalNode

from ..infrastructure.powerplant import Powerplant
from ..infrastructure.hospital import Hospital
from ..infrastructure.railroads import Railroad
from ..infrastructure.fuel_depot import FuelDepot
from ..infrastructure.water_treatment_plant import WaterTreatmentPlant

class StandardRegionNode(RegionalNode):
    """
    Baseline region: one of each core infrastructure site.
    """

    def build_sites(self):
        rn = self.region_name
        region_addr = self.address
        return [
            Powerplant("pp-1", rn, self.infra_addr("pp-1"), region_addr),
            Hospital("h-1", rn, self.infra_addr("h-1"), region_addr),
            Railroad("rr-1", rn, self.infra_addr("rr-1"), region_addr),
            FuelDepot("fd-1", rn, self.infra_addr("fd-1"), region_addr),
            WaterTreatmentPlant("wtp-1", rn, self.infra_addr("wtp-1"), region_addr),
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
