from backend.common.components.util import NetworkEntry

from .common import InfrastructureNode
from random import randint


class FuelDepot(InfrastructureNode):
    def __init__(self, entry: NetworkEntry, regions):
        super().__init__(entry=entry, regions=regions)
    # def __init__(self, name: str, region_name: str, region_address):
    #     super().__init__(network_name=name, name=name, region_name=region_name, region_address=region_address)
    #     self.name = name
    #     self.region_name = region_name
    #     self.resource_type = "Fuel Depot"
    #     self.resource_value = 100  # % fuel available
    #     print(f'MADE A NEW FUEL {self.name}')

    #     # self._con
    #     # self._net_connect(region_address)
    #     self.ready_to_handle()
    #     # self.connect(region_address)

    def get_resource_type(self):
        return "Fuel Depot"
    
    def generate_value(self):
        return randint(0, 100)
        # return super().generate_value()
        # return super().get_resource_type()