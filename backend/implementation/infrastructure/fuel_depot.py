from .common import InfrastructureNode

class FuelDepot(InfrastructureNode):
    def __init__(self, name: str, region_name: str, address, region_address):
        super().__init__(network_name=name, address=address, name=name, region_name=region_name)
        self.name = name
        self.region_name = region_name
        self.resource_type = "Fuel Depot"
        self.resource_value = 100  # % fuel available
        print(f'MADE A NEW FUEL {self.name}')

        # self._con
        self._net_connect(region_address)
        self.ready_to_handle()
        # self.connect(region_address)