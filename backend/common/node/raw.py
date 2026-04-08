from .template import NodeTemplate
from .networking.connection import ConnectionMap, ConnectionRegistry
# from .routing.router import Router, node_handler
from websockets.sync.server import serve
from websockets.sync.client import ClientConnection, connect as ws_connect
from websockets.sync.server import ServerConnection

from .networking.layers.net import NetLayer
from .networking.layers.routing import RoutingLayer, node_handler
from .networking.layers.dns import NameServiceLayer

class RawNode(NameServiceLayer):

    def __init__(
        self,
        network_name: str,
        address: tuple[str, int] = ('127.0.0.1', 0)
    ):
        super().__init__(network_name, address)


    # def _call_route(self):
        # return super()._call_route()

    # def _net_handle_msg(self, source, route, body):
    #     print(f'source={source}, route={route}, body={body}')
    #     pass
        # return super()._net_handle_msg(source, route

    def _net_on_connect_evt(self, name):
        pass

    def _net_on_disconnect_evt(self, name):
        pass

    def get_network_name(self):
        return self.network_name

   
    
    # def send_message(self, target, method, body, timeout = 2):
        # raise NotImplementedError()
    
    def shutdown(self):
        self.router.stop()
        raise NotImplementedError()
    



class Farkas(RawNode):

    @node_handler(name="hello")
    def hello(self, message: dict, sender: str):
        print(f'message: {message}')
        return {"pong": 1}

    @node_handler(internal_ms=400)
    def auo(self):

        if self.network_name == 'Hello':
            o = self.send_message('hello2', 'hello', {})
        
        # print("HELLO")
        # print(f'Self: {self}')
        # if self.has_connection("hello2"):
            # print("Yay!")
            
            # print(f'O: {o}')

class BasicDnsNode(RawNode):
    pass

if __name__ == "__main__":
    print("HI")

    dns = BasicDnsNode('dns', address=('127.0.0.1', 39))

    raw_a = Farkas("Hello")
    raw_b = Farkas("hello2")

    # raw_a._net_connect(('127.0.0.1', 8001))

    import time

    time.sleep(3)