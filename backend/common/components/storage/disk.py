

import os

from typing import Any

from pydantic import BaseModel

from backend.common.components.storage.backend import StorageBackend
from json import dump, load

class DiskBackend(StorageBackend):

    def __init__(
        self,
        name: str
    ):
        super().__init__()
        self.name = name

    def __root_path(self) -> str:
        return os.path.join('disk_cache', self.name)
    
    def write(
        self,
        table: str,
        key: str,
        value: Any
    ):
        if isinstance(value, BaseModel):
            value = value.model_dump()
        if not os.path.exists(self.__root_path()):
            os.makedirs(self.__root_path(), exist_ok=True)
        table_path: str = os.path.join(self.__root_path(), f'{table}.json')
        if not os.path.exists(table_path):
            with open(table_path, 'w') as fo:
                dump({}, fo, indent=4)
        with open(table_path, 'r') as fi:
            data_loaded = load(fi)  
        data_loaded[key] = value
        with open(table_path, 'w') as fo:
            dump(data_loaded, fo, indent=4)

        
        # return super().write(table, key, value)
    
    def read(
        self,
        table: str,
        key: str
    ) -> Any:
        table_path: str = os.path.join(self.__root_path(), f'{table}.json')
        if os.path.exists(table_path):
            with open(table_path, 'r') as fi:
                loaded = load(fi)
                if key not in loaded:
                    return None
                else:
                    return loaded[key]
                # return load(fi)[key]
        else:
            return None
        # return super().read(table, key)