from .plugin import Plugin
from ..routing import node_handler


class CapitalHeartbeatPlugin(Plugin):
    def __init__(self, host):
        super().__init__(host)

    @node_handler(name="api.proxy.region.heartbeat")
    def handle_region_heartbeat_proxy(self, message: dict, source: str):
        if not hasattr(self.host, "apply_region_heartbeat"):
            raise AttributeError("Capital heartbeat host must expose apply_region_heartbeat")

        origin = message.get("__origin_source", source)
        self.host.apply_region_heartbeat(message, origin)
        return {"status": "success"}

    @node_handler(name="api.region.heartbeat")
    def handle_region_heartbeat(self, message: dict, source: str):
        if not getattr(self.host, "is_leader", False):
            return {
                "status": "fail",
                "reason": f"not leader; current leader is {self.host.current_leader}"
            }

        if not hasattr(self.host, "proxy_region_heartbeat"):
            raise AttributeError("Capital heartbeat host must expose proxy_region_heartbeat")

        return self.host.proxy_region_heartbeat(message, source)