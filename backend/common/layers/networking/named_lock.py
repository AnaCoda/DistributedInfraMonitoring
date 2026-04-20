"""
Basically this class acts as a named lock whereby
we can prevent us 

"""

from contextlib import contextmanager
from threading import Lock
from typing import Dict

class NamedLock:

    def __init__(self):
        self.__map_lock = Lock()
        self.__map: Dict[str, Lock] = {}
        self.__ref_count: Dict[str, int] = {}

    @contextmanager
    def gate(self, name: str):
        # We begin by getting the lock.
        with self.__map_lock:
            if name in self.__map:
                lock = self.__map[name]
                self.__ref_count[name] += 1
            else:
                lock = Lock()
                self.__map[name] = lock
                self.__ref_count[name] = 1
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self.__map_lock:
                
                self.__ref_count[name] -= 1
                if self.__ref_count[name] == 0:
                    del self.__ref_count[name]
                    del self.__map[name]