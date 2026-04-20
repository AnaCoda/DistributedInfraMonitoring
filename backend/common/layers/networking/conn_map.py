


from threading import Lock
from typing import Dict, Optional

from pydantic import BaseModel

from backend.common.components.util import NetworkAddress, NetworkEntry, NetworkUrl
from backend.common.layers.networking.connection_map import ConnectionMap, ConnectionRegistry
from backend.common.layers.networking.named_lock import NamedLock
from backend.common.layers.networking.threadsafesocket import ThreadSafeSocket



class BetterConnectionMap:

    def __init__(self):
        self.__lock = Lock()
        self.__preallocations: Dict[str, NetworkEntry] = {}
        self.__cm = ConnectionMap()

    def preallocate(self, entry: NetworkEntry) -> bool:
        with self.__lock:
            if entry.name in self.__preallocations:
                return False
            self.__preallocations[entry.name] = entry
            return True
    
    def get_preallocation(self, name: str) -> Optional[NetworkEntry]:
        with self.__lock:
            return self.__preallocations[name]
        
    def register(self, name, entry: ConnectionRegistry):
        return self.__cm.register(name, entry)

    def deregister(self, target: str):
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

    