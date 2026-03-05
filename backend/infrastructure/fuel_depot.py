from .base_site import base_site
from .common import InfrastructureNode


class FuelDepot(InfrastructureNode):
    
    def __init__(self, network_name, region_name, address):
        super().__init__(network_name, address)
        
        self.name = network_name
        self.region_name = region_name
        self.address = address
        self.resource_value = 100 # % of fuel for the locale.
