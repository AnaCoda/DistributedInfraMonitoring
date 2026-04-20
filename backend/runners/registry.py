from json import dump, load
import logging
from os import path
import time
from typing import Dict
import filelock
from pydantic import BaseModel

from backend.common.components.util import NetworkAddress, NetworkEntry, NetworkUrl

PORT_ALLOCATION_START = 4000

class LocalRegistryJson(BaseModel):
    # The next available port to grab.
    available: int
    # The list of allocations.
    allocations: Dict[str, int]

class ServiceRegistry:
    """
    This allows us to assign unique ports to applications when we are running them locally.
    It uses file locks so that there is consensus on which application is assigned with port.
    """


    def __init__(self, is_local: bool):
        self.is_local = is_local
        if is_local:
            logging.info("Started local registry.")
        # self.get_port("hello")

    def __backend_dir(self) -> str:
        """
        The backend directory.

        Returns:
            str: The backend directory.
        """
        return path.join("backend", "runners")
        
    def __registry_path(self) -> str:
        return path.join(self.__backend_dir(), "local_registry.json")
    
    def __remote_registry_path(self) -> str:
        return path.join(self.__backend_dir(), "remote_registry.json")

    def __lock_path(self) -> str:
        return path.join(self.__backend_dir(), "local_registry.lock")
    
    def __dump(self, fo, reg: LocalRegistryJson):
        dump(reg.model_dump(mode='json'), fo, indent=4)
        
    def get_address(self, name: str) -> NetworkAddress | NetworkUrl:
        if self.is_local:
            return NetworkAddress(ip='0.0.0.0', port=self.get_port(name))
        else:
            with open(self.__remote_registry_path(), 'r') as fi:
                data = load(fi)
            if name not in data:
                raise RuntimeError(f'No remote registry for {name}. Please edit the {self.__remote_registry_path()} file in order to provide a registry entry.')
            return NetworkUrl(url=data[name])
        
    def service_is_local(self) -> bool:
        return self.is_local

    def get_port(self, name: str) -> int:
        """
        Gets an allocated port for the local service.

        Args:
            name (str): The name of the application.

        Returns:
            int: The allocated port.
        """
        lock = filelock.FileLock(self.__lock_path())
        with lock:
            if not path.exists(self.__registry_path()):
                with open(self.__registry_path(), 'w') as fo:
                    self.__dump(fo, LocalRegistryJson(available=PORT_ALLOCATION_START, allocations={}))
                    # dump(LocalRegistryJson(__PORT_ALLOCATION_START, {}).model_dump(mode='json'), fo, indent=4)
            with open(self.__registry_path(), 'r') as fi:
                reg = LocalRegistryJson.model_validate(load(fi))
            if name in reg.allocations:
                return reg.allocations[name]
            else:
                reg.allocations[name] = reg.available
                reg.available += 1
            with open(self.__registry_path(), 'w') as fo:
                self.__dump(fo, reg)
            return reg.available - 1
            
        

