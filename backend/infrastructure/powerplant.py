from .common import InfrastructureNode

class Powerplant(InfrastructureNode):
    def __init__(self, name: str, region_name: str, address, region_address):
        super().__init__(network_name=name, address=address, name=name, region_name=region_name, region_address=region_address)
        self.name = name
        self.region_name = region_name
        self.resource_type = "Powerplant"
        self.resource_value = "Stable" # is power stable, semi-stable, unstable or gone