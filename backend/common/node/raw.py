from .common.template import NodeTemplate
from .layers.networking.connection_map import ConnectionMap, ConnectionRegistry
# from .routing.router import Router, node_handler
from websockets.sync.server import serve
from websockets.sync.client import ClientConnection, connect as ws_connect
from websockets.sync.server import ServerConnection

from .layers.networking.networking_layer import NetLayer
from .layers.routing.routing_layer import RoutingLayer, node_handler
from .layers.dns.dns_layer import NameServiceLayer

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

    
from .common.events.connect import NodeConnectionType
from .common.plugins.replication.replication_plugin import ReplicationPlugin, NetEntry
from .common.storage.memory import MemoryStorageBackend

class Farkas(RawNode):

    def __init__(self, network_name, address = ('127.0.0.1', 0)):
        super().__init__(network_name, address)
        if network_name != 'bob':
            

            self.__rep_plugin = self.register_plugin(ReplicationPlugin(self, network_name, MemoryStorageBackend(), ['Hello', 'hello2']))
            self.__rep_plugin.set_leader('Hello')
        
        self.ready_to_handle()

    @node_handler(internal_ms=400)
    def hello(self):
        if self.get_network_name() == 'bob':
            # self.send_message('Hello', 'operate', { 'action': 'hello' })
            o = self.send_message('hello2', 'operate', { 'action': 'hello2' })
            print(f'O: {o}')
    
from .common.plugins.plugin import Plugin
from .common.plugins.leader_elec.bully_plugin import BullyPlugin

class TestBlugin(Plugin):
    
    @node_handler(internal_ms=400)
    def handle_blugin(self):
        print("BLG")

class BasicDnsNode(RawNode):
    def __init__(self, network_name, address = ('127.0.0.1', 0)):
        super().__init__(network_name, address)
        self.ready_to_handle()

        
        # self.register_plugin(TestBlugin())

if __name__ == "__main__":
    print("HI")
    try:
        dns = BasicDnsNode('dns', address=('127.0.0.1', 39))
        print("DNS UP")
        raw_a = Farkas("Hello")
        raw_b = Farkas("hello2")
        raw_c = Farkas('bob')

        # raw_a._net_connect(('127.0.0.1', 8001))

        import time

        time.sleep(4)
        # print("SHUTTING DOWN")
        raw_a.shutdown()
        time.sleep(2)
        print("FINISHING")
    except KeyboardInterrupt as e:
        pass
    dns.shutdown()
    raw_a.shutdown()
    raw_b.shutdown()
    raw_c.shutdown()