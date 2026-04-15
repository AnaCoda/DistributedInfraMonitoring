from dataclasses import dataclass
from threading import Lock
from .tss import ThreadSafeSocket


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
        with self.lock:
            # self.inbound_connections[name] = entry
            self.outbound_connections[name] = entry

    def deregister(self, target: str):
        with self.lock:
            if target in self.outbound_connections:
                try:
                    self.outbound_connections[target].connection.close()
                except Exception:
                    pass
                self.outbound_connections.pop(target, None)

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