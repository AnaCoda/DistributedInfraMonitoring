from dataclasses import dataclass
from threading import Lock
from .threadsafesocket import ThreadSafeSocket


@dataclass
class ConnectionRegistry:
    """
    The connection registry entry, which stores the
    connection object, the address, and the associated
    registry name.
    """
    name: str
    connection: ThreadSafeSocket

class ConnectionMap:

    def __init__(self):
        self.lock = Lock()
        # self.inbound_connections: dict[str, ConnectionRegistry] = {}
        self.outbound_connections: dict[str, ConnectionRegistry] = {}

    def register(self, name, entry: ConnectionRegistry):
        print(f'Registering connection for {name}')
        with self.lock:
            # self.inbound_connections[name] = entry
            # old = self.outbound_connections.get(name)
            # if old is not None and old.connection is not entry.connection:
            #     try:
            #         old.connection.close()
            #     except Exception:
            #         pass
            if name in self.outbound_connections:
                raise RuntimeError(f'Name {name} is ALREADY in the connection map.')
            self.outbound_connections[name] = entry

    def deregister(self, target: str):
        print(f'Deregistering connection for {target}')
        with self.lock:
            if target in self.outbound_connections:
                try:
                    self.outbound_connections[target].connection.close()
                except Exception:
                    pass
                self.outbound_connections.pop(target, None)

    def deregister_if_same(self, target: str, connection: ThreadSafeSocket) -> bool:
        with self.lock:
            entry = self.outbound_connections.get(target)
            if entry is None:
                return False
            if entry.connection is not connection:
                # A newer socket is now mapped for this target.
                return False

            self.outbound_connections.pop(target, None)
            try:
                connection.close()
            except Exception:
                pass
            return True

            # if target in self.inbound_connections:
            #     try:
            #         self.inbound_connections[target].connection.close()
            #     except Exception:
            #         pass
            #     self.inbound_connections.pop(target, None)

    # def has_inbound_connection(self, name: str):
    #     return self.has_outbound_connection(name)
    
    # def has_outbound_connection(self, name: str):
    #     with self.lock:
    #         return name in self.outbound_connections
    
    def has_connection(self, name: str):
        with self.lock:
            return (name in self.outbound_connections)

    def shutdown(self):
        with self.lock:
            for connection in list(self.outbound_connections.values()):
                connection.connection.close()
            # for connection in list(self.inbound_connections.values()):
            #     connection.connection.close()
                
    def get_connection_names(self):
        with self.lock:
            return list(self.outbound_connections.keys())
        

        
    def get_connection(self, name: str) -> ConnectionRegistry:
        with self.lock:
            return self.outbound_connections[name]