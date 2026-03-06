from .common import InfrastructureNode

class Railroad(InfrastructureNode):
    def __init__(self, name: str, region_name: str, address, region_address):
        super().__init__(network_name=name, address=address, name=name, region_name=region_name)
        self.name = name
        self.region_name = region_name
        self.resource_type = "Railroad"
        self.resource_value = "operational"  # operational, degraded, down

        self.connect(region_address)