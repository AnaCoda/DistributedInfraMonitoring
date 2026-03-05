from shared.node import NodeBase, node_handler, NodeConnectionType

# Mock tcp capital basically random bullshit go
class CapitalTcpNode(NodeBase):
    def __init__(self, network_name: str, address: tuple[str, int], national_store: dict, store_lock=None):
        super().__init__(network_name, address)
        self.national_store = national_store
        self.store_lock = store_lock

    @node_handler(name="infra.heartbeat")
    def infra_heartbeat(self, message: dict):
        """
        Expected message:
        {
          "name": "Alberta",
          "state": {...},
          "meta": {...}   # optional
        }
        """
        region = message.get("name")
        state = message.get("state")
        meta = message.get("meta", {})

        if not region or not state:
            return {"status": "fail", "reason": "missing name/state"}

        if self.store_lock:
            with self.store_lock:
                self.national_store[region] = {"state": state, "meta": meta}
        else:
            self.national_store[region] = {"state": state, "meta": meta}

        return {"status": "success"}

    @node_handler(on_connect=NodeConnectionType.INBOUND)
    def inbound_connect(self, name: str):
        print(f"[capital-tcp] inbound connection from {name}")

    @node_handler(on_disconnect=NodeConnectionType.INBOUND)
    def inbound_disconnect(self, name: str):
        print(f"[capital-tcp] inbound disconnected: {name}")