from .common import InfrastructureNode
from random import randint

class Hospital(InfrastructureNode):
    # def __init__(self, name: str, region_name: str, region_address):
    #     super().__init__(network_name=name, name=name, region_name=region_name, region_address=region_address)
    #     self.name = name
    #     self.region_name = region_name
    #     self.resource_type = "Hospital"
    #     self.resource_value = 100  # % beds available

    #     # self._net_connect(region_address)
    #     self.ready_to_handle()

    def get_resource_type(self):
        return "Hospital"
    
    def generate_value(self):
        return randint(0, 100)
        # return super().generate_value()
        # return super().get_resource_type()