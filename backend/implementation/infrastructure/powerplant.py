from random import choice

from backend.common.components.util import NetworkEntry

from .common import InfrastructureNode


class Powerplant(InfrastructureNode):
    def __init__(self, entry: NetworkEntry, regions):
        super().__init__(entry=entry, regions=regions)
    # def __init__(self, name: str, region_name: str, region_address):
    #     super().__init__(network_name=name, name=name, region_name=region_name, region_address=region_address)
    #     self.name = name
    #     self.region_name = region_name
    #     self.resource_type = "Powerplant"
    #     self.resource_value = "Stable" # is power stable, semi-stable, unstable or gone

    #     # connect to its region so broadcast_update has a target
    #     # self._net_connect(region_address)
    #     self.ready_to_handle()

    def get_resource_type(self):
        return "Powerplant"
    
    def generate_value(self):
        return choice(["stable", "unstable", "down"])
    # def generate_value(self):
        # return 
        # return super().generate_value()
    
        # return super().get_resource_type()