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

    
from .events.connect import NodeConnectionType


class Farkas(RawNode):

    @node_handler(name="hello")
    def hello(self, message: dict, sender: str):
        print(f'message: {message}')
        return {"pong": 1}
    
    # @node_handler(on_connect=NodeConnectionType.OUTBOUND)
    # def test(self, name: str):
    #     print('Hello')

    @node_handler(internal_ms=400)
    def auo(self):

        if self.network_name == 'Hello':
            print(f'Sending...')
            o = self.send_message('hello2', 'hello', {})
        
        # print("HELLO")
        # print(f'Self: {self}')
        if self.has_connection("hello2"):
            # print("Yay!")
            
            print(f'O: {o}')

class BasicDnsNode(RawNode):
    pass

if __name__ == "__main__":
    print("HI")
    try:
        dns = BasicDnsNode('dns', address=('127.0.0.1', 39))

        raw_a = Farkas("Hello")
        raw_b = Farkas("hello2")

        # raw_a._net_connect(('127.0.0.1', 8001))

        import time

        time.sleep(4)
        print("SHUTTING DOWN")
        raw_a.shutdown()
        time.sleep(2)
        print("FINISHING")
    except KeyboardInterrupt as e:
        pass
    dns.shutdown()
    raw_a.shutdown()
    raw_b.shutdown()