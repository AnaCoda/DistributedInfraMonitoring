from threading import Event, Thread
from dataclasses import dataclass
from typing import Optional, Callable

import json
from ..connection import ConnectionMap, ConnectionRegistry
from ...events.event import NodeEvent
from ..tss import ThreadSafeSocket

from websockets.sync.server import serve
from websockets.sync.client import ClientConnection, connect as ws_connect
from websockets.sync.server import ServerConnection

import websockets
from ...template import NodeTemplate

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
    stringified: str = json.dumps(body, default=lambda x : str(x))
    connection.sendall(stringified)
    
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
    if isinstance(body, bytes):
        body = body.decode('utf-8')
    return json.loads(body)
    

@dataclass
class EndpointResponse:
    """
    The endpoint response object which is the format used for handshaking.
    """
    status: str
    reason: Optional[str]
    body: dict

def _create_error(reason: str) -> dict:
    return {
        'status': 'fail',
        'reason': reason
    }

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


from abc import abstractmethod

from .routing import RoutingLayer

import uuid

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

from .helper.response import ResponseRegistryEntry, ResponseRegistrar

class NetLayer(RoutingLayer):

    def __init__(self, network_name: str, address: tuple[str, int]):
        super().__init__()
        self.network_name = network_name
        # self.address = address
        self.connection_map = ConnectionMap()
        self.dispatch_hook: Optional[Callable[..., ...]] = None

        self.response_registrar = ResponseRegistrar()

        self.launch_background_thread(self.listener, function_args=(address,))
        self._start_routing_layer()

    def get_network_name(self):
        return self.network_name
    

        # return super().get_network_name(

    # @abstractmethod
    def _net_on_connect_evt(self, name: str):
        # print("HI2")
        self._invoke_event(NodeEvent.ON_CONNECT, name)

    # @abstractmethod
    def _net_on_disconnect_evt(self, name: str):
        # print("HI3")
        # pass
        self._invoke_event(NodeEvent.ON_DISCONNECT, name)
    
    # @abstractmethod
    def _net_handle_msg(
        self,
        source: str,
        route: str,
        body: dict
    ):
        return self._call_route(
            source,
            route,
            body
        )
        # pass

    def has_connection(self, target):
        return self.connection_map.has_connection(target)
        # return super().has_connection(target)

    def __handle_recv_conn(
        self,
        socket: ThreadSafeSocket
    ) -> None:
        registry: dict = _recv_raw(socket)
        # print(f"recevied registry: {registry}")
        if 'name' not in registry:
            _send_raw(socket, _create_error('no registry name present'))
            socket.close()
            return
        name: str = registry['name']
        if self.connection_map.has_connection(name):
            _send_raw(socket, _create_error(f'connection already exists for {name}'))
            socket.close()
            return
        
        # Register the connection internally to keep track.
        self.connection_map.register(
            name=name,
            entry=ConnectionRegistry(
                name,
                connection=socket
            )
        )
        
        # print("HANDLE RECEIVE")
        self._net_on_connect_evt(name)
        # self._net_on_disconnect_evt(name)
        # self._on_network_event(NodeEvent.ON_CONNECT, name: str)
        # for evtha in self.event_maps[NodeEvent.ON_CONNECT]:
        #     if evtha.method == NodeConnectionType.INBOUND:
        #         evtha.functor(self, name)

        _send_raw(socket, { 'status': 'success', 'name': self.network_name })
        # print("DONE")
        self.__handle_registered_connection(name, socket)

    def __send_message_raw(
        self,
        connection: ThreadSafeSocket,
        method: str,
        body: dict,
        rid: Optional[str] = None
    ) -> MessagePackingResult:
        packed = MessagePackingResult.pack_msg(method, body, set_rid=rid)
        try:
            # print(f'Sending {packed.message}')
            _send_raw(connection, packed.message)
        except (websockets.exceptions.ConnectionClosedOK):
            raise
            # print(f'Tried to send a message along a websocket but it was closed.')
        except Exception as e:
            print(f'{type(e)}')
            print(f'ERROR: {e}, {method}, {body}')
            raise
        return packed

    def __send_message_targeted(
        self,
        target: str,
        method: str,
        body: dict,
        rid: Optional[str] = None,
        fire_and_forget: bool = False,
        timeout: Optional[float] = 2.0
    ):        # rid: str = str(uuid.uuid4()) if rid is None else rid
        # payload: dict = {
        #     'route': method,
        #     'rid': rid,
        #     'body': body
        # }
        # print(f'[{self.network_name}] -> {target}')
        # conn: ConnectionRegistry = self.outbound_connections[target]
        try:
            conn = self.connection_map.get_connection(target)
        except KeyError as exc:
            raise ConnectionError(f"No active connection to target {target}") from exc
        
        # Here we need to preallocate a response ID because we need
        # to register the response entry in-case the response comes
        # back extremely fast.
        rid: str = MessagePackingResult.generate_rid() if rid is None else rid
        if not fire_and_forget:
            ev: Event = self.response_registrar.register_event(rid)
            # ev: Event = Event()
            # self.response_registrar[rid] = ResponseRegistryEntry(
                # event=ev,
                # response=None
            # )
        
        packed = self.__send_message_raw(conn.connection, method, body, rid=rid)
        # print(f'Payload A: {payload}\nPayload B: {packed.message}')
        
        # print(f'[{self.network_name}, dest={conn.name}] Sending {packed.message}')
        if not fire_and_forget:
            # print('HEEOEE')
            success = ev.wait(timeout=timeout)
            # print(f'SuccesS: {success}')
            if not success:
                self.response_registrar.pop_registry(packed.rid)
                # if packed.rid in self.response_registrar:
                    # del self.response_registrar[packed.rid]
                raise TimeoutError(f"Timed out waiting for response from {target} on route {method}")

            # response: Optional[dict] = self.response_registrar[packed.rid].response
            # # print(f'Respo: {response}')
            # del self.response_registrar[packed.rid]
            response: Optional[dict] = self.response_registrar.pop_registry(packed.rid)
            return response

    def send_message_no_wait(self, target: str, method: str, body: dict):
        return self.__send_message_targeted(
            target=target,
            method=method,
            body=body,
            rid=None,
            fire_and_forget=True,
            timeout=0
        )

    def send_message(self, target, method, body, timeout = 2):
        return self.__send_message_targeted(target, method, body, rid=None, timeout=timeout)
        # return super().send_message(target, method, body, timeout)
            
    def __handle_routed_message(
        self,
        source: str,
        route: str,
        rid: str,
        body: dict,
        rc: ThreadSafeSocket
    ):
        try:
            #print(f"[{self.network_name}] handling route={route} from={source} body={body}")
            output = self._net_handle_msg(source, route, body)
            #print(f"[{self.network_name}] route={route} returned output={output}")

            response_body = {
                'status': 'success'
            } if output is None else output

        except Exception as e:
            print(f"[{self.network_name}] route crash on {route}: {type(e).__name__}: {e}")
            response_body = {
                'status': 'fail',
                'reason': f'{type(e).__name__}: {e}'
            }

        try:
            #print(f"[{self.network_name}] sending __response rid={rid} to={source} body={response_body}")
            if rc is not None:
                self.__send_message_raw(rc, '__response', response_body, rid=rid)
            else:
                self.__send_message_targeted(
                    source,
                    '__response',
                    rid=rid,
                    body=response_body,
                    fire_and_forget=True
                )
        except (
            ConnectionAbortedError,
            ConnectionResetError,
            BrokenPipeError,
            websockets.exceptions.ConnectionClosed,
        ) as e:
            print(f"[{self.network_name}] failed sending __response rid={rid} to={source}: {type(e).__name__}: {e}")
            try:
                if self.has_connection(source):
                    self.connection_map.deregister(source)
            except Exception:
                pass
            return
        except Exception as e:
            print(f"[{self.network_name}] unexpected send failure for __response rid={rid}: {type(e).__name__}: {e}")
            try:
                if self.has_connection(source):
                    self.connection_map.deregister(source)
            except Exception:
                pass
            return
            
    def _net_disconnect(self, name: str):
        self.connection_map.deregister(name)
        # self._net_disconnect(name)

    def _net_connect(self, address: tuple[str, int]):
        # print(f'Started Conn: {address}')
        connection = ThreadSafeSocket(ws_connect(f'ws://{address[0]}:{address[1]}'))
        # print(f'Yeyey')
        _send_raw(connection, { 'name': self.network_name })
        # print("SENT")
        
        body: dict = _recv_raw(connection)
        response: EndpointResponse = _unpack_response(body)
        if 'name' not in response.body:
            raise RuntimeError("No 'name' key in the response body.")
        target_name: str = response.body['name']
        if self.has_connection(target_name):
            # print('has conn?')
            connection.close()
            return
        #     return
        # print("HII")
        # self.outbound_connections[target_name] = ConnectionRegistry(
        #     name=target_name,
        #     connection=connection,
        # )
        self.connection_map.register(target_name, ConnectionRegistry(target_name, connection))
        # self.__register_duplex_connection(target_name, ConnectionRegistry(target_name, connection))
        
                
        def con_handle(connection):
            self.__handle_registered_connection(target_name, connection)

        self.launch_background_thread(con_handle, function_args=(connection,))
        self._net_on_connect_evt(target_name)

    def __handle_registered_connection(
        self,
        name: str,
        connection: ThreadSafeSocket
    ):
        
        try:
            while not self.stop_event.is_set():
                message = _recv_raw(connection)
                # print(f'Recv\'d Message: {message}')
                if 'route' not in message:
                    raise RuntimeError('No "route" key in the received payload.')
                if 'rid' not in message:
                    raise RuntimeError('No "rid" key in the received payload.')
                if 'body' not in message:
                    raise RuntimeError('No "body" key in the received payload.')
                route: str = message['route']
                rid: str = message['rid']
                if route == '__response':
                    # Set the event.
                    #print(f"[{self.network_name}] received __response rid={rid} body={message['body']}")
                    self.response_registrar.answer_registry(rid, message['body'])
                elif route.startswith("api.proxy."):
                    # Preserve in-order replica application from a single sender connection.
                    self.__handle_routed_message(name, route, rid, message['body'], connection)
                else:
                    self.launch_background_thread(
                        self.__handle_routed_message,
                        function_args=(name, route, rid, message['body'], connection)
                    )
        except (
            ConnectionAbortedError,
            ConnectionResetError,
            websockets.exceptions.ConnectionClosedOK
        ):
            pass
        finally:
            self._net_on_disconnect_evt(name)
            self.connection_map.deregister(name)
            
            # except NodeRpcError as nre:
            #     packed = MessagePackingResult.pack_msg('__response', { 'status': 'fail', 'reason': nre.message }, set_rid=message['rid'])
                
            #     _send_raw(connection, packed.message)

    def listener(self, address: tuple[str, int]):
        def connection_handler(connection):
            # Wrap the connection in a thread safe socket and proceed.
            self.__handle_recv_conn(ThreadSafeSocket(connection))
        with serve(connection_handler, address[0], address[1]) as server:
            self.server = server
            self.address = (address[0], server.socket.getsockname()[1])
            server.serve_forever()

    def shutdown(self):
        # Make a best-effort attempt to shutdown
        # the server connection.
        try:
            self.server.shutdown()
        except Exception:
            pass

        # Deregister and close all active connections.
        for name in self.connection_map.get_connection_names():
            self.connection_map.deregister(name)
        super().shutdown()
    
