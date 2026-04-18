from ..shared.node import NodeBase, node_handler
# from ..common.node.raw import RawNode, node_handler


class InfrastructureNode(NodeBase):
    def __init__(self, network_name, address, name=None, region_name=None):
        super().__init__(network_name, address)

        # Always have sane defaults
        self.name = name if name is not None else network_name
        self.region_name = region_name

        self.resource_type = None
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

    @node_handler(internal_ms=3000)
    def broadcast_update(self):
        # Don't crash the interval thread if something is half-initialized
        try:
            payload = self.to_dict()
        except Exception as e:
            print(f"[{self.network_name}] broadcast_update skipped: {e}")
            return

        # print(f"[{self.network_name}] broadcasting {payload}")

        # Removed region filter since the names arent standard in setup.py
        # TODO: region filter after name standardization
        for peer_name in self.connection_map.get_outbound_names():
            self.send_message(peer_name, "api.report", payload)