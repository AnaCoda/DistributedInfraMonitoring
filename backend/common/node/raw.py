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
from .common.plugins.replication.replication_plugin import ReplicationPlugin
from .common.storage.memory import MemoryStorageBackend

class Farkas(RawNode):

    def __init__(self, network_name, backend, address = ('127.0.0.1', 0)):
        super().__init__(network_name, address)
        if network_name != 'bob':
            

            self._rep_plugin = self.register_plugin(ReplicationPlugin(
                host=self,
                name=network_name,
                backend=backend,
                replicas=['Hello', 'hello2'],
                routes=[
                    ('sussy', self.sussy)
                ]
            ))
            self._rep_plugin.set_leader('Hello')
        
        self.count = 0
        self.ready_to_handle()
        
        if network_name != 'bob':
            self.test_load = { 'list': [] }
            
            loaded = self._rep_plugin.load_state()
            if loaded is not None:
                self.test_load = loaded
            
        # self.register_route('sussy', self.sussy)

    def sussy(self, body: dict):
        # print(f'[{self.network_name}] hi')
        self.test_load['list'].append(body['action'])
        self._rep_plugin.commit(self.test_load)
        print(f'[{self.network_name}] test_load={self.test_load}')
        # print(f'[{self.network_name}] Sussy was called {body}.')

    @node_handler(internal_ms=400)
    def hello(self):
        if self.get_network_name() == 'bob':
            self.send_message('Hello', 'sussy', { 'action': self.count })
            # o = self.send_message('hello2', 'sussy', { 'action': self.count })
            # print(f'O: {o}')
            self.count += 1
    
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
    b_ms = MemoryStorageBackend()
    try:
        dns = BasicDnsNode('dns', address=('127.0.0.1', 39))
        print("DNS UP")
        raw_a = Farkas("Hello", MemoryStorageBackend())
        
        raw_c = Farkas('bob', MemoryStorageBackend())

        # raw_a._net_connect(('127.0.0.1', 8001))


        import time

        print(f'Other fakas node coming online...')
        raw_b = Farkas("hello2", b_ms)

        time.sleep(5)
        print(f'hello2 going down...')
        raw_b.shutdown()
        time.sleep(4)
        print(f'hello2 is back')
        raw_b = Farkas('hello2', b_ms)

        time.sleep(10)
        # print("SHUTTING DOWN")
        # raw_a.shutdown()
        # time.sleep(2)
        print("FINISHING")
    except KeyboardInterrupt as e:
        pass
    dns.shutdown()
    raw_a.shutdown()
    raw_b.shutdown()
    raw_c.shutdown()