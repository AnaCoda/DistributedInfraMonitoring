from typing import Callable, Optional, Any
import inspect
from threading import Thread, Event, Lock
import time
import socket
import json
from dataclasses import dataclass
from enum import Enum
import uuid
import io
from websockets.sync.server import serve
from websockets.sync.client import ClientConnection, connect as ws_connect
from websockets.sync.server import ServerConnection
import websockets

class ThreadSafeSocket:
    """
    A thread-safe socket object that protects the writing end of the
    connection to prevent interleaved writes.
    
    These are separated as reading and writing is something we want
    to happen all the time on a duplex connection, and so they
    must be handled separately.
    """
    websocket: ServerConnection
    write_lock: Lock
    
    def __init__(self, sock: ServerConnection):
        """
        Creates a new thread safe socket object.

        Args:
            sock (socket.socket): The socket object that
            we wish to wrap.
        """
        self.raw_socket = sock
        self.write_lock = Lock()
        self.closed = False
        
    def sendall(self, data: bytes):
        """
        Sends all the bytes across the socket.

        Args:
            data (bytes): The data to send over the socket.
        """
        with self.write_lock:
            self.raw_socket.send(data, text=True)
            
    def recv(self, data: int) -> bytes:
        """
        Receives a certain number of bytes over the
        thread safe socket.

        Args:
            data (int): The length of bytes we want to read.

        Returns:
            bytes: The byte buffer we received.
        """
        out = self.raw_socket.recv()
        if type(out) == bytes:
            return out
        # print(out)
        
        return out.encode('utf-8')
    
    @staticmethod
    def connect(address: tuple[str, int]):
        
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(address)
        return ThreadSafeSocket(sock)
    
    
    @staticmethod
    def create_listener(address: tuple[str, int]):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(address)
        sock.listen()
        return ThreadSafeSocket(sock)
    
    def accept(self) -> tuple["ThreadSafeSocket", tuple[str, int]]:
        conn, addr = self.raw_socket.accept()
        return ThreadSafeSocket(conn), addr
    
    def close(self):
        """
        Closes the thread safe socket.
        """
        if not self.closed:
            # We want to make sure we only
            # call close once, although I'm not
            # necessarily sure if this makes a difference.
            try:
                self.raw_socket.close()
            except OSError as e:
                print(f'Failed to close socket: {e}')
                return
            self.closed = True


class NodeEvent(Enum):
    """
    The node event type.
    """
    ON_CONNECT = 0
    ON_DISCONNECT = 1

@dataclass
class NodeRpcError(Exception):
    """
    This exception indicates that there were problems executing a remote
    procedure call with the node.
    """
    message: str


class NodeConnectionType(Enum):
    """
    The connection type of the event, i.e., if it is an inbound or an outbound
    event.
    """
    INBOUND = 0
    OUTBOUND = 1
    
@dataclass
class ResponseRegistryEntry:
    """
    This allows a response pattern (full-duplex communication over single connection)
    """
    event: Event
    response: Optional[dict]
    
@dataclass
class EndpointResponse:
    """
    The endpoint response object which is the format used for handshaking.
    """
    status: str
    reason: Optional[str]
    body: dict

@dataclass
class ConnectionRegistry:
    """
    The connection registry entry, which stores the
    connection object, the address, and the associated
    registry name.
    """
    name: str
    connection: ThreadSafeSocket
    
@dataclass
class EventOnConnectRegistry:
    """
    Registers an event handler for the OnConnect event.
    There are two variants defined by method:
        INBOUND: We have received a connection.
        OUTBOUND: We have made a connection with an outbound
        client.
    """
    functor: Callable[["NodeBase", str], None]
    method: NodeConnectionType

@dataclass
class EventOnDisconnectRegistry:
    """
    Registers an event handler for the OnDisconnect event.
    There are two variants defined by method:
        INBOUND: We have received a connection.
        OUTBOUND: We have made a connection with an outbound
        client.
    """
    functor: Callable[["NodeBase", str], None]
    method: NodeConnectionType

def _send_raw(connection: ThreadSafeSocket, body: dict):
    """
    Using a ThreadSafeSocket object, this will send a dictionary
    object across the connection.

    Args:
        connection (ThreadSafeSocket): The thread safe socket object
        used for sending and receiving data.
        body (dict): The actual message that should be sent over
        the socket.
    """
    stringified: str = json.dumps(body)
    # length_bytes: bytes = len(stringified).to_bytes(length=4, byteorder='little', signed=False)
    connection.sendall(stringified.encode('utf-8'))
    
def _recv_raw(connection: ThreadSafeSocket) -> dict:
    """
    Receives a JSON dictionary across the wire. This could
    be improved with a library like protobuf.

    Args:
        connection (ThreadSafeSocket): The connection that should
        be used for receiving.

    Raises:
        ConnectionAbortedError: If the length received is 0, then
        we return this error which simplifies error handling.

    Returns:
        dict: The JSON message.
    """
    # length = int.from_bytes(connection.recv(4), byteorder='little', signed=False)
    body = connection.recv(0)
    # if len(body) == 0:
        # raise ConnectionAbortedError()
        
    return json.loads(body.decode('utf-8'))
    


def _unpack_response(body: dict) -> EndpointResponse:
    """
    Unpacks a status response. This method is generally used
    for unpacking the handshake sequence but may have various
    other uses.

    Args:
        body (dict): The total payload to unpack.

    Raises:
        RuntimeError: Failed to unpack the status response because it was
        malformed.

    Returns:
        EndpointResponse: The response from the endpoint we are trying
        to connect to.
    """
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

@dataclass
class MessagePackingResult:
    """
    Represents a packed message that is ready for sending.
    """
    message: dict
    rid: str
    
    @staticmethod
    def generate_rid() -> str:
        """
        Generates a new response ID string from a UUIDv4.

        Returns:
            str: The response ID string.
        """
        return str(uuid.uuid4())
    
    @staticmethod
    def pack_msg(
        route: str,
        body: dict,
        set_rid: Optional[str] = None
    ) -> "MessagePackingResult":
        """
        This packs a message in the common format of the protocol,
        we do this to keep things simple and keep the protocol simple
        and allow maximal code reuse and reduce the testing surface area.

        Args:
            route (str): The method we want to call on the remote object.
            body (dict): The body of the call, also known as the parameters.
            set_rid (Optional[str], optional): Sets the response ID of the request, if not it will be generated. Defaults to None.

        Returns:
            MessagePackingResult: The packed message along with the rid we ended up
            using.
        """
        rid: str = str(uuid.uuid4()) if set_rid is None else set_rid
        return MessagePackingResult(
            message={
                'route': route,
                'rid': rid,
                'body': body
            },
            rid=rid
        )



class NodeBase:
    """
    The basic node name providing connection details
    and allowing the simple sending and receiving of messages.
    """
    network_name: str
    routing_dict: dict = {}
    stop_event: Event = Event()
    server: socket.socket = None
    
    event_maps = {
        'on_connect': []
    }
    
    def __init__(self, network_name: str, address: tuple[str, int]):
        self.network_name = network_name
        self.address = address
        
        self.routing_dict = {}
        self.inbound_connections: dict[str, ConnectionRegistry] = {}
        self.outbound_connections: dict[str, ConnectionRegistry] = {}
        self.stop_event = Event()
        self.server = None
        self.event_maps: dict[NodeEvent, list[Any]] = {
            NodeEvent.ON_CONNECT: [],
            NodeEvent.ON_DISCONNECT: []
        }
        
        self.response_registrar = {}
        

        for _, fn in inspect.getmembers(self.__class__, predicate=inspect.isfunction):
            annotations: dict = fn.__annotations__
            if 'node_route' in annotations:
                # We have a node route.
                route: str = annotations['node_route']['name']
                self.routing_dict[route] = fn
            elif 'interval_functor' in annotations:
                interval: int = annotations['interval_functor']['interval']
                self.__launch_interval_functor(fn, interval)
            elif 'on_connect' in annotations:
                self.event_maps[NodeEvent.ON_CONNECT].append(EventOnConnectRegistry(
                    functor=fn,
                    method=annotations['on_connect']
                ))
            elif 'on_dc' in annotations:
                self.event_maps[NodeEvent.ON_DISCONNECT].append(EventOnDisconnectRegistry(
                    functor=fn,
                    method=annotations['on_dc']
                ))
                
        def connection_handler(connection):
            self.__handle_conn_recv(ThreadSafeSocket(connection))
                
        
        
        def listener():
            with serve(connection_handler, address[0], address[1]) as server:
                self.server = server
                server.serve_forever()
            # self.server = ThreadSafeSocket.create_listener(self.address)
            # while True:
            #     try:
            #         conn, addr = self.server.accept()
            #         # conn = ThreadSafeSocket(conn)
            #         self.__launch_background_thread(connection_handler, fargs=(conn, addr))
            #     except OSError as e:
            #         if e.winerror == 10038:
            #             break
            #         else:
            #             print(e)
                



        self.__launch_background_thread(listener)
        

        
    def __handle_registered_connection(self, name: str, connection: ThreadSafeSocket):
        while True:
            try:
                message = _recv_raw(connection)
                self.__dispatch_received_message(name, message)
            except (ConnectionAbortedError, ConnectionResetError, websockets.exceptions.ConnectionClosedOK):
                for evtha in self.event_maps[NodeEvent.ON_DISCONNECT]:
                    if evtha.method == NodeConnectionType.INBOUND:
                        evtha.functor(self, name)
                self.__deregister_duplex_connection(name)
                break
            except NodeRpcError as nre:
                packed = MessagePackingResult.pack_msg('__response', { 'status': 'fail', 'reason': nre.message }, set_rid=message['rid'])
                
                _send_raw(connection, packed.message)
    
    def __handle_conn_recv(self, connection: ThreadSafeSocket):
        registry = _recv_raw(connection)
        print(f"recevied registry: {registry}")
        if 'name' not in registry:
            _send_raw(connection, { 'status': 'fail', 'reason': 'no registry name present' })
            connection.close()
            return
        name: str = registry['name']
        if name in self.inbound_connections:
            _send_raw(connection, { 'status': 'fail', 'reason': 'name currently in use.' })
            connection.close()
            return
        
        # Register the connection internally to keep track.
        self.__register_duplex_connection(name, ConnectionRegistry(name, connection))

        

        
        for evtha in self.event_maps[NodeEvent.ON_CONNECT]:
            if evtha.method == NodeConnectionType.INBOUND:
                evtha.functor(self, name)
        
        print("SENDING")
        _send_raw(connection, { 'status': 'success', 'name': self.network_name })
        print("DONE")
        self.__handle_registered_connection(name, connection)
        
    def __dispatch_received_message(
        self,
        source: str,
        payload: dict
    ):
        print(f'[{self.network_name}] Received {payload}')
        if 'route' not in payload:
            raise NodeRpcError('No "route" key in the received payload.')
        if 'rid' not in payload:
            raise NodeRpcError("No 'rid' key in the received payload.")
        route: str = payload['route']
        rid: str = payload['rid']
        if route == '__response':
            # Set the event.
            self.response_registrar[rid].event.set()
            self.response_registrar[rid].response = payload['body']
        else:
            output = self.__call_route(payload)
            if output is None:
                
                self.__send_message_targeted(source, '__response', rid=rid, body={
                    'status': 'success'
                }, fire_and_forget=True)
            else:
                self.__send_message_targeted(source, '__response', rid=rid, body=output, fire_and_forget=True)
            
    def __register_duplex_connection(self, target: str, entry: ConnectionRegistry):
        self.outbound_connections[target] = entry
        self.inbound_connections[target] = entry

    def __deregister_duplex_connection(self, target: str):
        if target in self.outbound_connections:
            self.outbound_connections[target].connection.close()
            del self.outbound_connections[target]
        if target in self.inbound_connections:
            self.inbound_connections[target].connection.close()
            del self.inbound_connections[target]
                
    def disconnect(self, name: str):
        
        self.__deregister_duplex_connection(name)
        for evtha in self.event_maps[NodeEvent.ON_DISCONNECT]:
            if evtha.method == NodeConnectionType.OUTBOUND:
                evtha.functor(self, name)
                
    def connect(self, address: tuple[str, int]):
        # connection: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # connection.connect(address)
        # connection = ThreadSafeSocket.connect(address)
        connection = ThreadSafeSocket(ws_connect(f'ws://{address[0]}:{address[1]}'))
        

        # self.__send_message_targeted(target=)
        # self.__send_message_raw()
        _send_raw(connection, { 'name': self.network_name })
        
        body: dict = _recv_raw(connection)
        response: EndpointResponse = _unpack_response(body)
        if 'name' not in response.body:
            raise RuntimeError("No 'name' key in the response body.")
        target_name: str = response.body['name']
        self.outbound_connections[target_name] = ConnectionRegistry(
            name=target_name,
            connection=connection,
        )
        
        for name in self.event_maps[NodeEvent.ON_CONNECT]:
            evtha: dict = name
            if evtha.method == NodeConnectionType.OUTBOUND:
                evtha.functor(self, target_name)
                
        def con_handle(connection):
            self.__handle_registered_connection(target_name, connection)
                
        self.__launch_background_thread(con_handle, fargs=(connection,))
        
                
    def __launch_background_thread(self, functor, fargs = None):
        # TODO: Investigate how to make daemonless.
        if fargs is None:
            Thread(target=functor, daemon=True).start()
        else:
            Thread(target=functor, args=fargs, daemon=True).start()
        

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
        self.server.shutdown()

        for connection in self.outbound_connections.values():
            connection.connection.close()
        for connection in self.inbound_connections.values():
            connection.connection.close()
        for event in self.response_registrar.values():
            event.event.set()

    def __call_route(self, message: dict) -> Optional[dict]:
        """
        Takes a message and forwards it to the correct handler method.

        Args:
            message (dict): The message

        Raises:
            NodeRpcError: The packet was malformed whcih prevented proper routing.

        Returns:
            Optional[dict]: The optional response object, which may be null.
        """
        if 'route' not in message:
            raise NodeRpcError('Could not find the "route" key in message.')
        if 'body' not in message:
            raise NodeRpcError('Could not find the "body" key in message.')
        route: str = message['route']
        body: dict = message['body']
        if route in self.routing_dict:
            return self.routing_dict[route](self, body)
        else:
            raise NodeRpcError(f'Could not find route {route}')
        
    # def __send_internal_raw(
    #     self,
    #     connection: ConnectionRegistry,
    #     body: dict
    # ) -> None:
        
        
    def __send_message_raw(
        self,
        connection: ThreadSafeSocket,
        method: str,
        body: dict,
        rid: Optional[str] = None
    ) -> MessagePackingResult:
        packed = MessagePackingResult.pack_msg(method, body, set_rid=rid)
        _send_raw(connection, packed.message)
        return packed
    
    def send_message(
        self,
        target: str,
        method: str,
        body: dict
    ):
        return self.__send_message_targeted(target, method, body, rid=None, fire_and_forget=False)
    
    def __send_message_targeted(self, target: str, method: str, body: dict, rid: Optional[str] = None, fire_and_forget: bool = False):
        # rid: str = str(uuid.uuid4()) if rid is None else rid
        # payload: dict = {
        #     'route': method,
        #     'rid': rid,
        #     'body': body
        # }
        
        conn: ConnectionRegistry = self.outbound_connections[target]
        
        # Here we need to preallocate a response ID because we need
        # to register the response entry in-case the response comes
        # back extremely fast.
        rid: str = MessagePackingResult.generate_rid() if rid is None else rid
        if not fire_and_forget:
            ev: Event = Event()
            self.response_registrar[rid] = ResponseRegistryEntry(
                event=ev,
                response=None
            )
        
        packed = self.__send_message_raw(conn.connection, method, body, rid=rid)
        # print(f'Payload A: {payload}\nPayload B: {packed.message}')
        
        print(f'[{self.network_name}] Sending {packed.message}')
        if not fire_and_forget:
            ev.wait()
            response: Optional[dict] = self.response_registrar[packed.rid].response
            del self.response_registrar[packed.rid]
            return response
    
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
        return {
            "ping": "pong"
        }
        
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
        print(f'Disconnection event from {name} [inbound]')
        
    @node_handler(on_disconnect=NodeConnectionType.OUTBOUND)
    def outbound_dc(self, name):
        print(f'Disconnection event from {name} [outbound]')
    
# model_A = Test(network_name="CentralA", address=('127.0.0.1', 3000))
# model_B = Test(network_name="CentralB", address=('127.0.0.1', 3001))

# def a():
#     print('Started TestA')
    
#     # model.call({
#         # "route": "api.call",
#         # "body": {
#             # "hello": "world"
#         # }
#     # })
    
    
# def b():
#     print('Started TestA')
#     model_B.connect(('127.0.0.1', 3000))
    
#     print('Msg 1:', model_B.send_message(target='CentralA', method='api.call', body={
#         'hello': 'world'
#     }))
#     # print("DONEZO!")
    
#     # model_B.send_message(target='CentralA', method='api.call2', body={
#     #     'hello': 'world'
#     # })
    
    
#     # time.sleep(0.5)
#     # model_B.disconnect(name='CentralA')
#     # model = Test(network_name="Central", address=('127.0.0.1', 3000))
#     # model.call({
#     #     "route": "api.call",
#     #     "body": {
#     #         "hello": "world"
#     #     }
#     # })
    
    

# Thread(target=a).start()

# Thread(target=b).start()


# try:
#     while True:
#         time.sleep(0.2)
# except KeyboardInterrupt:
#     print("STOPPING")
#     model_A.shutdown()
#     model_B.shutdown()