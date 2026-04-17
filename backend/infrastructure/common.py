from ..shared.node import NodeBase, node_handler


class InfrastructureNode(NodeBase):
    def __init__(self, network_name, address, name=None, region_name=None, region_address=None):
        # Set fields before NodeBase launches interval handlers.
        self.name = name if name is not None else network_name
        self.region_name = region_name
        self.region_address = region_address

        super().__init__(network_name, address)

        self.resource_type = None
        self.resource_value = None

        if getattr(self, "region_address", None) is not None:
            self._ensure_region_connection()

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

    @node_handler(name="admin.node.outage_control")
    def handle_node_outage_control(self, msg: dict):
        return NodeBase.handle_node_outage_control(self, msg)

    @node_handler(internal_ms=3000)
    def broadcast_update(self):
        if self.is_outage_active():
            return

        self._ensure_region_connection()
        if self.region_name and not self.has_connection(self.region_name):
            return

        # Don't crash the interval thread if something is half-initialized
        try:
            payload = self.to_dict()
        except Exception as e:
            print(f"[{self.network_name}] broadcast_update skipped: {e}")
            return

        # print(f"[{self.network_name}] broadcasting {payload}")

        # Removed region filter since the names arent standard in setup.py
        # TODO: region filter after name standardization
        for peer_name in list(self.outbound_connections.keys()):
            self.send_message(peer_name, "api.report", payload)

    def _ensure_region_connection(self):
        region_address = getattr(self, "region_address", None)
        region_name = getattr(self, "region_name", None)
        if region_address is None or region_name is None:
            return
        if self.has_connection(region_name):
            return

        try:
            self.connect(region_address)
        except Exception:
            # Retry on next interval.
            pass