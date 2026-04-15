import threading
from threading import Lock, Event
from typing import Optional
from dataclasses import dataclass

@dataclass
class ResponseRegistryEntry:
    """
    This allows a response pattern (full-duplex communication over single connection)
    """
    event: Event
    response: Optional[dict]

class ResponseRegistrar:

    def __init__(self):
        self.registrar: dict[str, ResponseRegistryEntry] = {}
        self.registrar_lock = Lock()

    def register_event(
        self,
        rid: str
    ) -> Event:
        """
        Registers a new response slot in the map and returns the
        object that should be waited on.

        Args:
            rid (str): The RID.

        Returns:
            Event: The event that when set indicates that we
            have received a response.
        """
        ev = Event()
        with self.registrar_lock:
            self.registrar[rid] = ResponseRegistryEntry(ev, None)
        return ev
    
    def answer_registry(
        self,
        rid: str,
        response: dict       
    ):
        """
        Provides a response to a response with a specific RID.

        Args:
            rid (str): The response RID.
            response (dict): The response body.
        """
        with self.registrar_lock:
            if rid in self.registrar:
                self.registrar[rid].event.set()
                self.registrar[rid].response = response
    
    def pop_registry(
        self,
        rid: str
    ) -> Optional[dict]:
        """
        Pops the registry entry associated with the specific RID.

        Args:
            rid (str): The RID we want to test out.

        Returns:
            Optional[dict]: The response object if there is one.
        """
        with self.registrar_lock:
            value = self.registrar[rid]
            del self.registrar[rid]
            return value.response
        
    
   