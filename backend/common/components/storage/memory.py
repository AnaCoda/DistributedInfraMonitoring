from typing import Any
from .backend import StorageBackend

class MemoryStorageBackend(StorageBackend):

    def __init__(self):
        super().__init__()
        self.tables: dict[str, dict[str, Any]] = {}



    def write(self, table, key, value):
        if table not in self.tables:
            self.tables[table] = {}
        self.tables[table][key] = value

    def read(self, table, key):
        if table not in self.tables:
            return None
        table_lk = self.tables[table]
        if key not in table_lk:
            return None
        return table_lk[key]
        # return super().read(table, key)
    

        # return super().write(table, key, value)