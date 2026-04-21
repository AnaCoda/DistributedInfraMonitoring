from ..template import NodeTemplate


class Plugin(NodeTemplate):
    def __init__(self, host: NodeTemplate):
        super().__init__()
        self.host = host

    def launch_background_thread(self, functor, function_args):
        return self.host.launch_background_thread(functor, function_args)
        # return super().launch_background_thread(functor, function_args)

    def _register_route(self, route, functor):
        self.host._register_route(route, functor)
        # return super()._register_route(route, functor)

    def is_shutting_down(self):
        return self.host.is_shutting_down()
        # return super().is_shutting_down()

    def wait_ready(self):
        return self.host.wait_ready()
        # return super().wait_ready()

    def get_network_name(self):
        return self.host.get_network_name()

    def has_connection(self, target):
        return self.host.has_connection(target)

    def send_message(self, target, method, body, timeout=5):
        return self.host.send_message(target, method, body, timeout)

    def send_message_no_wait(self, target, method, body):
        return self.host.send_message_no_wait(target, method, body)

    def _try_connect(self, address):
        return self.host._try_connect(address)
    
    def disconnect(self, name: str):
        return self.host.disconnect(name)
        # return super()._try_connect(address)

    # def connect(self, address):
    #     if hasattr(self.host, "connect"):
    #         print(f'CONNPATH_A')
    #         return self.host.connect(address)
    #     if hasattr(self.host, "_connect_to"):
    #         print(f'CONNPATH_B')
    #         return self.host._connect_to(address)
    #     if hasattr(self.host, "_net_connect"):
    #         print(f'CONNPATH_C')
    #         try:
    #             return self.host._net_connect(address)
    #         except Exception as e:
    #             print(f'MEGA FAILE')
    #     raise AttributeError("Host node does not expose a connect method")

    # def disconnect(self, name):
    #     if hasattr(self.host, "disconnect"):
    #         return self.host.disconnect(name)
    #     if hasattr(self.host, "_disconnect_name"):
    #         return self.host._disconnect_name(name)
    #     if hasattr(self.host, "_net_disconnect"):
    #         return self.host._net_disconnect(name)
    #     raise AttributeError("Host node does not expose a disconnect method")

    def send_message_no_wait(self, target, method, body):
        return self.host.send_message_no_wait(target, method, body)

    def shutdown(self):
        pass