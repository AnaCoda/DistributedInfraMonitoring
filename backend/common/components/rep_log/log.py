from dataclasses import dataclass, asdict as asdict_dc, is_dataclass

from pydantic import BaseModel
from ..storage.backend import StorageBackend
from typing import Optional
from .operation import Operation
from threading import Lock

@dataclass
class _LogState:
    sequence_position: int

class ReplicationOutOfOrder(Exception):
    pass

def asdict(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode='json')
    elif is_dataclass(obj):
        return asdict_dc(obj)


class ReplicationLog:

    def __init__(self, backend: StorageBackend):
        self.log_lock = Lock()
        self.backend = backend
        self.log_state = _LogState(0)

        current_state = self.backend.read('meta', 'state')
        if current_state is None:
            self.__write_back_log_state()
            # self.backend.write('meta', 'state', asdict(self.log_state))
        elif current_state is not None:
            self.log_state = _LogState(**current_state)

    def get_sequence_pos(self) -> int:
        """
        Returns the sequence position of the replication log.

        Returns:
            int: The sequence position of the replication log.
        """
        return self.log_state.sequence_position
    
    def __write_back_log_state(self):

        self.backend.write('meta', 'state', asdict(self.log_state))

    def add_log(self, operation: Operation):
        with self.log_lock:
            if operation.sequence_number != self.get_sequence_pos() + 1:
                raise ReplicationOutOfOrder()
            self.backend.write('logs', operation.sequence_number, asdict(operation))
            self.log_state.sequence_position = operation.sequence_number
            self.__write_back_log_state()
        
    def __retrieve_at_idxs(self, idcs: list[int]) -> list[Operation]:
        return [ Operation(**self.backend.read('logs', op)) for op in idcs ]

    def retrieve_at_idxs(self, idcs: list[int]) -> list[Operation]:
        with self.log_lock:
            return self.__retrieve_at_idxs(idcs)

    def retrieve_logs(self, start: Optional[int], end: Optional[int]):
        with self.log_lock:
            if self.get_sequence_pos() == 0:
                return []
            if end is None or self.get_sequence_pos() < end:
                end = self.get_sequence_pos() + 1
            else:
                end += 1
            if start is None:
                start = 1
          
            return self.__retrieve_at_idxs(list(range(start, end)))

    def retrieve_all_logs(self):
        return self.retrieve_logs(None, None)
    

        