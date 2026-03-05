from ..shared.node import NodeBase, node_handler


class InfrastructureNode(NodeBase):
    def __init__(self, network_name, address):
        super().__init__(network_name, address)
        self.resource_type = None
        self.name = None
        self.region_name = None
        self.resource_value = None
    
    def get_name(self):
        return self.name
    
        
    def get_resource_type(self):
        return self.resource_type
    
    def to_dict(self):
        return {
            "name": self.name,
            "region_name": self.region_name,
            "resource_type": self.resource_type,
            "resource_value": self.resource_value
        }
    
    @node_handler(internal_ms=500)
    def broadcast_update(self):
        for name, registry in self.outbound_connections.items():
            if 'region' in name:
                self.send_message(name, 'api.report', self.to_dict())
        
   
