from threading import Lock
from ..networking.networking_layer import NetLayer
from dataclasses import dataclass, asdict
from ..routing.routing_layer import RoutingLayer, node_handler
from time import sleep

@dataclass
class NameRegistry:
    """
    The name registry object, housing the IP and the port.
    """
    name: str
    ip: str  
    port: int


class NameServiceLayer(NetLayer):
    """
    The name service layer object extends the network layer and provides
    the DNS service which allows us to connect automatically to targets
    without having th
    """

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

    def _net_on_disconnect_evt(self, name):
        with self.name_registry_lock:
            if name in self.name_registry:
                del self.name_registry[name]
            # print(f'POST-DELETE [{self.network_name}] <- ({name}): {self.name_registry}')
        super()._net_on_disconnect_evt(name)
        # return super()._net_on_disconnect_evt(name)

    def __safe_connect(self, name, registry: NameRegistry):
        if not self.has_connection(name):
            try:
                self._net_connect((registry.ip, registry.port))
            except RuntimeError as e:
                pass

    

    def __dns_outreach(self, target):
        if self.network_name == 'dns':
            return
        
        with self.name_registry_lock:
            net_reg_items = list(self.name_registry.items())

        # print(f'FLAG A')
        for name, registry in net_reg_items:
            if 'dns' not in name:
                continue
            # print('FLAG B')
            self.__safe_connect(name, registry)
            # print('FLAG C')
            # print(f'Name: {name}')
            result = self.send_message(
                target=name,
                method='dns.lookup',
                body={
                    '__this': asdict(NameRegistry(self.network_name, self.address[0], self.address[1])),
                    '__search': target
                } 
            )
            # print('FLAG D')
            for name in result:
                result = NameRegistry(**name)
                self.__add_dns(result)
            # print(f'FLAG E')

    def __get_self_registry_details(self):
        return NameRegistry(
            name=self.network_name,
            ip=self.address[0],
            port=self.address[1]
        )

    @node_handler(internal_ms=500)
    def handle_dns_ping(self):
        if self.network_name == 'dns':
            return
        
        with self.name_registry_lock:
            net_reg_items = list(self.name_registry.items())

        for name, registry in net_reg_items:
            if 'dns' not in name:
                continue
            self.__safe_connect(name, registry)
            self.send_message(
                target=name,
                method='dns.register',
                body=asdict(self.__get_self_registry_details())
            )
        

    def __add_dns(self, registry: NameRegistry):
        if registry.name == self.network_name:
            return
        
        if registry.name not in self.name_registry:
            self.name_registry[registry.name] = registry
            # print(f'New Registry: {self.name_registry[registry.name]}')
            with self.guard_map_lock:
                self.guard_map[registry.name] = Lock()
            # print(f'[{self.network_name}] {self.name_registry}')


    
    @node_handler(name='dns.register')
    def handle_dns_register(self, message: dict):
        self.__add_dns(NameRegistry(**message))

    @node_handler(name='dns.lookup')
    def handle_dns_lookup(self, message: dict):
        # print(f'DNS LOOKUP {message}')
        # registry = 
        self_details = message['__this']

        self.__add_dns(NameRegistry(**self_details))
       
        results= [asdict(d) for k, d in self.name_registry.items() if k == message['__search']]
        # print(f'Results: {results}')
        # print(f'Results: {}')
        return results

    def __lookup_registry(self, name: str) -> NameRegistry | None:
        # for name in self.name_registry.i
        if name not in self.name_registry:
            return None
        return self.name_registry[name]
        # return None



    def send_message(self, target, method, body, timeout=2):
        # with self.__get_guard_map_lock(target):
        if not self.has_connection(target):
           
            for _ in range(3):
                # print(f'DNS OUTREACH')
                self.__dns_outreach(target)
                # print(f'DONE!')
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
