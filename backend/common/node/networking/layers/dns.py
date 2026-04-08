from threading import Lock
from .net import NetLayer
from dataclasses import dataclass, asdict
from .routing import RoutingLayer, node_handler
from time import sleep

@dataclass
class NameRegistry:
    name: str
    ip: str
    port: int


class NameServiceLayer(NetLayer):

    def __init__(self, network_name, address):
        super().__init__(network_name, address)


        self.name_service_backoff_loop = 0.5

        self.guard_map = {}
        self.guard_map_lock = Lock()
        

        self.name_registry_lock = Lock()
        self.name_registry: dict[str, NameRegistry] = {
            
        }

        self.__add_dns(NameRegistry(
                'dns',
                '127.0.0.1',
                39
            ))

        # if self.get_network_name() == 'dns':

        self.launch_background_thread(self.__dns_outreach, None)

    def __safe_connect(self, name, registry: NameRegistry):
        if not self.has_connection(name):
            try:
                self._net_connect((registry.ip, registry.port))
            except RuntimeError as e:
                pass
    def __dns_outreach(self):
        if self.network_name == 'dns':
            return
        
        with self.name_registry_lock:
            net_reg_items = list(self.name_registry.items())

        for name, registry in net_reg_items:
            
            self.__safe_connect(name, registry)
            # print(f'Name: {name}')
            result = self.send_message(
                target=name,
                method='dns.lookup',
                body=asdict(NameRegistry(self.network_name, self.address[0], self.address[1])) 
            )
            for name in result:
                result = NameRegistry(**name)
                self.__add_dns(result)


    @node_handler(internal_ms=500)
    def handle_dns_ping(self):
        self.__dns_outreach()
        # print("DNS")
        

    def __add_dns(self, registry: NameRegistry):
        if registry.name == self.network_name:
            return
        
        if registry.name not in self.name_registry:
            self.name_registry[registry.name] = registry
            with self.guard_map_lock:
                self.guard_map[registry.name] = Lock()
            # print(f'[{self.network_name}] {self.name_registry}')


    def __get_guard_map_lock(self, name: str) -> Lock:
        with self.guard_map_lock:
            if name not in self.guard_map:
                self.guard_map[name] = Lock()
            return self.guard_map[name]


    @node_handler(name='dns.lookup')
    def handle_dns_lookup(self, message: dict):
        # registry = 
        self.__add_dns(NameRegistry(**message))
       
        return [asdict(d) for d in self.name_registry.values()]

    def __lookup_registry(self, name: str) -> NameRegistry | None:
        # for name in self.name_registry.i
        if name not in self.name_registry:
            return None
        return self.name_registry[name]
        # return None



    def send_message(self, target, method, body, timeout=2):
        with self.__get_guard_map_lock(target):
            if not self.has_connection(target):
                for _ in range(3):
                    registry = self.__lookup_registry(target)
                    if registry is None:
                        sleep(self.name_service_backoff_loop)
                        continue
                    if self.has_connection(target):
                        break
                    self.__safe_connect(registry.name, registry)
                    sleep(0.1)
                if not self.has_connection(target):
                    raise RuntimeError("COULD NOT LOCATE")
            
        return super().send_message(target, method, body, timeout)

    # @node_handler(name="dns.lookup")
    # def handle_dns_register(self, name):
    #     # self.__register_name(name)


    # @node_handler(name="dns")
