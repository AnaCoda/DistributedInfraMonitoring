from .patch import Patch
from typing import Optional
from dataclasses import dataclass, asdict
import heapq

@dataclass
class VersionedPatch(Patch):
    version: int

    def __init__(self, version: int, patch: Patch):
        super().__init__(patch.actions)
        self.version = version

    @staticmethod
    def diff(version, original: dict, updated: dict):
        return VersionedPatch(version, Patch.diff(original, updated))

    def to_dict(self):
        return asdict(self)
    
    @staticmethod
    def from_dict(obj):
        if 'actions' in obj:
            return VersionedPatch(version=obj['version'], patch=Patch.from_dict(obj))
        return VersionedPatch(**obj)

from copy import deepcopy

@dataclass
class StateHistory:
    version: int
    patch: Patch
    rewind: Patch

class ManagedState:
    __internal: dict

    version: int
    last_applied_update: int
    update_queue: list

    history: list[tuple[int, VersionedPatch]]

    def __init__(self, version: int):
        self.__internal = {}
        self.version = version
        self.update_queue = []
        self.last_applied_update = version

        self.history = []
   

    @staticmethod
    def from_dict(version: int, obj: dict):
        
        src = ManagedState(version)
        src.__internal = deepcopy(obj)
        return src
    
    def is_consistent(self):
        ovr = []
        status = True
        expected = self.version + 1
        while len(self.history) != 0:
            vr, hs = heapq.heappop(self.history)
            ovr.append((vr, hs))
            # print(f'VR: {vr}')
            if vr != expected:
                status = False
                break
            expected += 1
            
            
        for item in ovr:
            heapq.heappush(self.history, item)
        return status
    
    def start_transaction(self) -> dict:
        return deepcopy(self.inspect_dict())
    
    def end_transaction(self, obj: dict, apply: bool = False) -> Optional[VersionedPatch]:
        patch = VersionedPatch.diff(-1, self.__internal, obj)
        if len(patch.actions) == 0:
            return None
        else:
            
            # self.version += 1

            patch.version = self.version + 1
            if apply:
                # print(f'Apply {apply}')
                self.__apply_patch(patch)
            return patch
        # self.version += 1
        # return VersionedPatch.diff(self.version + 1, original=)
    
    def fast_forward(self, version: int, obj: dict):
        self.version = version
        self.__internal = obj

    def __apply_patch(self, patch: VersionedPatch):
        heapq.heappush(self.history, (patch.version, patch))
        if self.is_consistent():
            # print(f'consistent')
            while len(self.history) != 0:
                vr, hs = heapq.heappop(self.history)
                hs.apply_inplace(self.__internal)
                self.version = vr

    def apply_update(self, patch: VersionedPatch):
        if patch.version <= self.version:
            # Discard update.
            return
        else:
            self.__apply_patch(patch)
                
        # print(f'Applying patch_version={patch.version}, current={self.last_applied_update}')

        # rewound: bool = False
        # if patch.version < self.last_applied_update:
        #     print(f'Rewinding!')
        #     rewound = True
        #     # We need to rewind my friend!
        #     overflow = []
        #     while True:
        #         vr, history = heapq.heappop(self.history)
                
        #         print(f'Vr: {vr}')

        #         print(f'Current: {self.__internal}')
                
        #         print(f'Post rewind: {self.__internal}')

        #         # Make sure we can restore this.
        #         overflow.append((vr, history))
        #         if history.version == self.last_applied_update:
        #             print("DONE!")
        #             break
        #         history.rewind.apply_inplace(self.__internal)
         
        #     print(f'Post rewind: {self.__internal}')

        # self.last_applied_update = patch.version

        # rewinder = patch.apply_inplace(self.__internal, get_rewind=True)
        # print(f'version={patch.version}, rewinder: {rewinder}')
 
        

    def inspect_dict(self) -> dict:
        return self.__internal