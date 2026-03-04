from typing import Callable, Optional
import inspect
from threading import Thread, Event
import time
import socket
import json
from dataclasses import dataclass
from enum import Enum


class NodeConnectionType(Enum):
    INBOUND = 0
    OUTBOUND = 1

def _send_raw(connection: socket.socket, body: dict):
    stringified: str = json.dumps(body)
    length_bytes: bytes = len(stringified).to_bytes(length=4, byteorder='little', signed=False)
    connection.sendall(length_bytes + stringified.encode('utf-8'))
    
def _recv_raw(connection: socket.socket) -> dict:
    length = int.from_bytes(connection.recv(4), byteorder='little', signed=False)
    body = connection.recv(length)
    if len(body) == 0:
        raise ConnectionAbortedError()
    return json.loads(body.decode('utf-8'))
    # connection.sendall(len(stringified))
    
@dataclass
class EndpointResponse:
    status: str
    reason: Optional[str]
    body: dict

@dataclass
class ConnectionRegistry:
    name: str
    connection: socket.socket
    address: tuple[str, int]
    
    
@dataclass
class EventOnConnectRegistry:
    functor: Callable[["NodeBase", str], None]
    method: NodeConnectionType
    
@dataclass
class EventOnDisconnectRegistry:
    functor: Callable[["NodeBase", str], None]
    method: NodeConnectionType

def _unpack_response(body: dict) -> EndpointResponse:
    if 'status' in body:
        status: str = body['status']
        if status == 'fail':
            if 'reason' in body:
                reason: str = body['reason']
                raise RuntimeError(f'Server refused to accept connection with reason: {reason}')
            else:
                raise RuntimeError('Server reported a status of "fail" but failed to provide a reason. Server is not following format correctly.')
        elif status == 'success':
            return EndpointResponse(status, body['reason'] if 'reason' in body else None, body=body)
        else:
            raise RuntimeError(f'Unknown status value: "{status}"')
    else:
        raise RuntimeError('Server did not have the "status" key in the message body, indicating that the server is not following the protocol format.')

class NodeBase:
    """
    The basic node name providing connection details
    and allowing the simple sending and receiving of messages.
    """
    network_name: str
    routing_dict: dict = {}
    inbound_connections: dict = {}
    outbound_connections: dict = {}
    stop_event: Event = Event()
    server: socket.socket = None
    
    event_maps = {
        'on_connect': []
    }
    
    def __init__(self, network_name: str, address: tuple[str, int]):
        self.network_name = network_name
        self.address = address
        
        self.routing_dict = {}
        self.inbound_connections = {}
        self.outbound_connections = {}
        self.stop_event = Event()
        self.server = None
        self.event_maps = {
            'on_connect': [],
            'on_dc': []
        }
        

        for _, fn in inspect.getmembers(self.__class__, predicate=inspect.isfunction):
            annotations: dict = fn.__annotations__
            if 'node_route' in annotations:
                # We have a node route.
                route: str = annotations['node_route']['name']
                self.routing_dict[route] = fn
            elif 'interval_functor' in annotations:
                interval: int = annotations['interval_functor']['interval']
                # print(interval)
                self.__launch_interval_functor(fn, interval)
            elif 'on_connect' in annotations:
                # print(self.event_maps['o'])
                self.event_maps['on_connect'].append(EventOnConnectRegistry(
                    functor=fn,
                    method=annotations['on_connect']
                ))
            elif 'on_dc' in annotations:
                self.event_maps['on_dc'].append(EventOnDisconnectRegistry(
                    functor=fn,
                    method=annotations['on_dc']
                ))
                
        def connection_handler(connection, address):
            registry = _recv_raw(connection)
            if 'name' not in registry:
                _send_raw(connection, { 'status': 'fail', 'reason': 'no registry name present' })
                connection.close()
                return
            name: str = registry['name']
            if name in self.inbound_connections:
                _send_raw(connection, { 'status': 'fail', 'reason': 'name currently in use.' })
                connection.close()
                return
            self.inbound_connections[name] = ConnectionRegistry(
                name=name,
                connection=connection,
                address=address
            )
            

            
            for evtha in self.event_maps['on_connect']:
                # evtha: dict = name
                if evtha.method == NodeConnectionType.INBOUND:
                    evtha.functor(self, name)
                # functor(self)

            _send_raw(connection, { 'status': 'success', 'name': self.network_name })
            
            while True:
                try:
                    message = _recv_raw(connection)
                    self.call(message)
                except ConnectionAbortedError:
                    for evtha in self.event_maps['on_dc']:
                        if evtha.method == NodeConnectionType.INBOUND:
                            evtha.functor(self, name)
                    break
            # pass
            
        
        
        def listener():
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.bind(self.address)
            self.server.listen()
            while True:
                try:
                    conn, addr = self.server.accept()
                    self.__launch_background_thread(connection_handler, fargs=(conn, addr))
                except OSError as e:
                    # print(e.winerror)
                    if e.winerror == 10038:
                        break
                    else:
                        print(e)
                    # break
                
        self.__launch_background_thread(listener)
                
    def disconnect(self, name: str):
        if name in self.outbound_connections:
            self.outbound_connections[name].connection.close()
            del self.outbound_connections[name]
        for evtha in self.event_maps['on_dc']:
            if evtha.method == NodeConnectionType.OUTBOUND:
                evtha.functor(self, name)
                
    def connect(self, address: tuple[str, int]):
        connection: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection.connect(address)

        
        _send_raw(connection, { 'name': self.network_name })
        
        body: dict = _recv_raw(connection)
        response: EndpointResponse = _unpack_response(body)
        if 'name' not in response.body:
            raise RuntimeError("No 'name' key in the response body.")
        target_name: str = response.body['name']
        self.outbound_connections[target_name] = ConnectionRegistry(
            name=target_name,
            connection=connection,
            address=address
        )
        
        for name in self.event_maps['on_connect']:
            evtha: dict = name
            if evtha.method == NodeConnectionType.OUTBOUND:
                evtha.functor(self, target_name)
        
                
    def __launch_background_thread(self, functor, fargs = None):
        if fargs is None:
            Thread(target=functor).start()
        else:
            Thread(target=functor, args=fargs).start()
        

    def __launch_interval_functor(self, functor, interval):
        """
        Launches an interval function.

        Args:
            functor (_type_): _description_
            interval (_type_): _description_
        """
        def runnable():
            while not self.stop_event.is_set():
                functor(self)
                time.sleep(interval / 1000.0)
        self.__launch_background_thread(runnable)
        
    def shutdown(self):
        self.stop_event.set()
        self.server.close()
        
        
        for connection in self.outbound_connections.values():
            connection.connection.close()
        for connection in self.inbound_connections.values():
            connection.connection.close()
    
            

    def call(self, message: dict):
        """
        Takes a message and forwards it to the correct handler method.

        Args:
            message (dict): _description_

        Raises:
            RuntimeError: _description_
            RuntimeError: _description_
            RuntimeError: _description_

        Returns:
            _type_: _description_
        """
        if 'route' not in message:
            raise RuntimeError('Could not find the "route" key in message.')
        if 'body' not in message:
            raise RuntimeError('Could not find the "body" key in message.')
        route: str = message['route']
        body: dict = message['body']
        if route in self.routing_dict:
            return self.routing_dict[route](self, body)
        else:
            raise RuntimeError(f'Could not find route {route}')
        
    
    def send_message(self):
        pass
    
def node_handler(name: str = None, internal_ms: int = None, on_connect: NodeConnectionType = None, on_disconnect: NodeConnectionType = None):
    if name is not None and internal_ms is not None:
        raise RuntimeError("Both 'name' and 'internal_ms' cannot be set.")
    if name is not None:
        def decorator(fn):
            fn.__annotations__['node_route'] = {
                "name": name,
                "functor": fn
            }
            return fn
        return decorator
    elif internal_ms is not None:
        def decorator(fn):
            fn.__annotations__['interval_functor'] = {
                "interval": internal_ms,
                "functor": fn
            }
            return fn
        return decorator
    elif on_connect is not None:
        def decorator(fn):
            fn.__annotations__['on_connect'] = on_connect
            return fn
        return decorator
    elif on_disconnect is not None:
        def decorator(fn):
            fn.__annotations__['on_dc'] = on_disconnect
            return fn
        return decorator
    else:
        raise RuntimeError("You must specify at least one mode of operation.")
    
    
class Test(NodeBase):
    
    def __init__(self, network_name, address):
        super().__init__(network_name, address)
        

    @node_handler(name='api.call')
    def hello(self, message: dict):
        print(message)
        
    @node_handler(internal_ms=1000)
    def good_morning(self):
        print("helloo")
        
    @node_handler(on_connect=NodeConnectionType.INBOUND)
    def inbound(self, name):
        print(f"hello, received connection from {name}")
    
    @node_handler(on_connect=NodeConnectionType.OUTBOUND)
    def outbound(self, name):
        print(f'Hello, I have made an outbound to {name}')
        
        
    @node_handler(on_disconnect=NodeConnectionType.INBOUND)
    def inbound_dc(self, name):
        print(f'Disconnection event from {name}')
    
model_A = Test(network_name="CentralA", address=('127.0.0.1', 3000))
model_B = Test(network_name="CentralB", address=('127.0.0.1', 3001))

def a():
    
    # model.call({
        # "route": "api.call",
        # "body": {
            # "hello": "world"
        # }
    # })
    print(f'Started TestA')
    
def b():
    model_B.connect(('127.0.0.1', 3000))
    
    time.sleep(0.5)
    model_B.disconnect(name='CentralA')
    # model = Test(network_name="Central", address=('127.0.0.1', 3000))
    # model.call({
    #     "route": "api.call",
    #     "body": {
    #         "hello": "world"
    #     }
    # })
    print(f'Started TestA')
    

Thread(target=a).start()

Thread(target=b).start()


try:
    for i in range(3):
        time.sleep(1)
except KeyboardInterrupt:
    model_A.shutdown()
    model_B.shutdown()