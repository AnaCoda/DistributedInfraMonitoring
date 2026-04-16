# from .base_site import base_site
from .common import InfrastructureNode

class WaterTreatmentPlant(InfrastructureNode):

    # Pass up to base_site then define self as a water_treatment_plant
    def __init__(self, name: str, region_name: str, address, region_address):
        super().__init__(network_name=name, address=address, name=name, region_name=region_name, region_address=region_address)
        self.name = name
        self.region_name = region_name
        self.resource_type = "Water Treatment Plant"
        self.resource_value = 100           # % of water needed for locale being produced
