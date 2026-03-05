from .base_site import base_site
from .common import InfrastructureNode


class Railroad(InfrastructureNode):
    
    def __init__(self, network_name, address):
        super().__init__(network_name, address)
        self.resource_type = "Railroad"
        self.resource_value = "Operational" # operational, semi-operational, or non-operational
