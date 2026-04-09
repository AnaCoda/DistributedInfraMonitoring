from ....template import NodeTemplate

class Plugin(NodeTemplate):
    pass

    def get_network_name(self):
        pass
        # return super().get_network_name()

    def has_connection(self, target):
        pass

    def send_message(self, target, method, body, timeout = 2):
        pass

    def shutdown(self):
        pass
        # return super().send_message(target, method, body, timeout)
        # return super().has_connection(targe