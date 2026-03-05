from .base_site import base_site
from .common import InfrastructureNode

class Powerplant(InfrastructureNode):
    def __init__(self, network_name, address):
        super().__init__(network_name, address)
        self.resource_type = "Powerplant"
        self.resource_value = "Stable" # is power stable, semi-stable, unstable or gone

