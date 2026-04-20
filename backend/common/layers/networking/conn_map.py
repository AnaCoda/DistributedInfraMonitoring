


from threading import Lock
from typing import Dict

from pydantic import BaseModel

from backend.common.components.util import NetworkAddress, NetworkEntry, NetworkUrl
from backend.common.layers.networking.connection_map import ConnectionMap, ConnectionRegistry
from backend.common.layers.networking.threadsafesocket import ThreadSafeSocket



class BetterConnectionMap:

    def __init__(self):
        self.__lock = Lock()
        self.__preallocations: Dict[str, NetworkEntry] = {}
        self.__cm = ConnectionMap()
        # self.__cm

    def preallocate(self, entry: NetworkEntry) -> bool:
        with self.__lock:
            if entry.name in self.__preallocations:
                return False
            self.__preallocations[entry.name] = entry
            return True
        
    def register(self, name, entry: ConnectionRegistry):
        return self.__cm.register(name, entry)

    def dereigster(self, target: str):
        return self.__cm.deregister(target)
    
    def has_connection(self, name: str):
        return self.__cm.has_connection(name)
    
    def deregister_if_same(self, target: str, connection: ThreadSafeSocket) -> bool:
        return self.__cm.deregister_if_same(target, connection)

    def shutdown(self):
        self.__cm.shutdown()

    def get_connection_names(self):
        return self.__cm.get_connection_names()
    
    def get_connection(self, name: str) -> ConnectionRegistry:
        return self.__cm.get_connection(name)
    
    # def realize_connection()

    