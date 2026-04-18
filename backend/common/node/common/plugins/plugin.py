from ..template import NodeTemplate


class Plugin(NodeTemplate):
    def __init__(self, host: NodeTemplate):
        super().__init__()
        self.host = host

    def wait_ready(self):
        return self.host.wait_ready()
        # return super().wait_ready()

    def get_network_name(self):
        return self.host.get_network_name()

    def has_connection(self, target):
        return self.host.has_connection(target)

    def send_message(self, target, method, body, timeout=2):
        return self.host.send_message(target, method, body, timeout)

    def send_message_no_wait(self, target, method, body):
        return self.host.send_message_no_wait(target, method, body)

    def connect(self, address):
        if hasattr(self.host, "connect"):
            return self.host.connect(address)
        if hasattr(self.host, "_connect_to"):
            return self.host._connect_to(address)
        if hasattr(self.host, "_net_connect"):
            return self.host._net_connect(address)
        raise AttributeError("Host node does not expose a connect method")

    def disconnect(self, name):
        if hasattr(self.host, "disconnect"):
            return self.host.disconnect(name)
        if hasattr(self.host, "_disconnect_name"):
            return self.host._disconnect_name(name)
        if hasattr(self.host, "_net_disconnect"):
            return self.host._net_disconnect(name)
        raise AttributeError("Host node does not expose a disconnect method")

    def send_message_no_wait(self, target, method, body):
        return self.host.send_message_no_wait(target, method, body)

    def shutdown(self):
        pass