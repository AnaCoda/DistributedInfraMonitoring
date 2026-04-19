# from .base_site import base_site
from .common import InfrastructureNode

class WaterTreatmentPlant(InfrastructureNode):

    def get_resource_type(self):
        return "Water Treatment Plant"
        # return super().get_resource_type()

    # # Pass up to base_site then define self as a water_treatment_plant
    # def __init__(self, name: str, region_name: str, region_address):
    #     super().__init__(network_name=name, name=name, region_name=region_name, region_address=region_address)
    #     self.name = name
    #     self.region_name = region_name
    #     self.resource_type = "Water Treatment Plant"
    #     self.resource_value = 100           # % of water needed for locale being produced

    #     # self._net_connect(region_address)
    #     self.ready_to_handle()