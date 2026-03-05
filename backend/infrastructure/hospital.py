from .base_site import base_site
from .common import InfrastructureNode

class Hospital(InfrastructureNode):
    def __init__(self, network_name, region_name: str, address):
        super().__init__(network_name, address)
        self.name = network_name
        self.resource_type = 'Hospital'
        
        # % of hospital for the populace
        self.resource_value = 100
        
        self.region_name = region_name
        
        
        

