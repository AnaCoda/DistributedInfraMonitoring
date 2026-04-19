from abc import ABC, abstractmethod
from typing import Optional, Any

class StorageBackend(ABC):

    @abstractmethod
    def write(self, table: str, key: str, value: Any) -> None:
        pass

    @abstractmethod
    def read(self, table: str, key: str) -> Optional[Any]:
        pass