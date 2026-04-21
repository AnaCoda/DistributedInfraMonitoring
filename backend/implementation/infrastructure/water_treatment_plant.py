# from .base_site import base_site
from random import randint

from backend.common.components.util import NetworkEntry

from .common import InfrastructureNode

class WaterTreatmentPlant(InfrastructureNode):
    def __init__(self, entry: NetworkEntry, regions):
        super().__init__(entry=entry, regions=regions)


    def get_resource_type(self):
        return "Water Treatment Plant"
        # return super().get_resource_type()

    def generate_value(self):
        return randint(0, 100)

    # # Pass up to base_site then define self as a water_treatment_plant
    # def __init__(self, name: str, region_name: str, region_address):
    #     super().__init__(network_name=name, name=name, region_name=region_name, region_address=region_address)
    #     self.name = name
    #     self.region_name = region_name
    #     self.resource_type = "Water Treatment Plant"
    #     self.resource_value = 100           # % of water needed for locale being produced

    #     # self._net_connect(region_address)
    #     self.ready_to_handle()