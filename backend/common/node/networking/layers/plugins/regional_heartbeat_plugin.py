from .plugin import Plugin
from ..routing import node_handler


class RegionalHeartbeatPlugin(Plugin):
    def __init__(self, host, interval_ms: int = 1000):
        super().__init__(host)
        self.interval_ms = interval_ms

    @node_handler(internal_ms=1000)
    def heartbeater(self):
        if not hasattr(self.host, "_outbound_names"):
            return

        if not any(name.startswith("rm-") for name in self.host._outbound_names()):
            return

        if not hasattr(self.host, "_send_to_capital"):
            raise AttributeError("Regional heartbeat host must expose _send_to_capital")

        self.host._send_to_capital("api.region.heartbeat", {"status": "ok"})