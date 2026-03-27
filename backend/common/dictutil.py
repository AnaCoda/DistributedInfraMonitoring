from __future__ import annotations
from typing import Any
from enum import Enum

source = {
    "good": "morning",
    "people": {
        "homer": 1
    }
}

new = {
    "bad": "day",
    "people": {
        "seth": 2
    }
}

def _recurse_merge_dict(source: dict, new: dict):
    for k, v in new.items():
        # Case 1: We do not even have this key.
        if k not in source:
            source[k] = v
        else:
            # Case 2: We DO have this key.
            if isinstance(v, dict) and isinstance(source[k], dict):
                # Case 2A: Both are dictionaries, so we recursively merge.
                _recurse_merge_dict(source[k], v)
            else:
                # Case 2B: They are not both dictionaries, therefore override with this key.
                source[k] = v
            

def merge_dictionaries(source: dict, new: dict):
    _recurse_merge_dict(source, new)

class PatchOp(Enum):
    NEW_FIELD = 0
    DEL_FIELD = 1
    EDIT_FIELD = 2
    PATCH_ARRAY = 3

from dataclasses import asdict, dataclass

# PATCH_ACTION_REGISTRY
@dataclass
class PatchAction:
    op: PatchOp
    path: str

    def __init__(self, op: PatchOp, path: str):
        self.op = op
        self.path = path

    def apply(self, target: dict):
        raise NotImplementedError("Have not implemented the apply method!")
    

def _locate_patch(path: str, target: dict) -> tuple[dict, str]:
    if '.' not in path:
        return target, path
    route: list[str] = path.split('.')
    for r in route[:-1]:
        target = target[r]
    return target, route[-1]

@dataclass
class PatchAddKey(PatchAction):
    value: Any

    def __init__(self, path, value: Any):
        super().__init__(PatchOp.NEW_FIELD, path)
        self.value = value

    def apply(self, target: dict):
        trg, name = _locate_patch(self.path, target)
        trg[name] = self.value
    
@dataclass
class PatchDeleteKey(PatchAction):
    def __init__(self, path: str):
        super().__init__(PatchOp.DEL_FIELD, path)

    def apply(self, target: dict):
        trg, name = _locate_patch(self.path, target)
        del trg[name]

@dataclass
class PatchEditField(PatchAction):
    value: Any

    def __init__(self, path: str, value: Any):
        super().__init__(PatchOp.EDIT_FIELD, path)
        self.value = value

    def apply(self, target: dict):
        trg, name = _locate_patch(self.path, target)
        trg[name] = self.value

@dataclass
class PatchArray(PatchAction):
    index_sets: dict[int, Any]
    end: int

    def __init__(self, path: str, end: int, index_sets: dict[int, Any]):
        super().__init__(PatchOp.PATCH_ARRAY, path)

        # On occasion, we may receive a dictionary of type dict[str, Any],
        # in this case we will try our best to parse it back to the correct form.
        if isinstance(list(index_sets.keys())[0], str):
            # print("YES")
            index_sets = { int(k): v for k, v in index_sets.items() }

        self.end = end
        self.index_sets = index_sets

    def apply(self, target):
        trg, name = _locate_patch(self.path, target)
        trg[name] = trg[name][:self.end]
        for idx, val in self.index_sets.items():
            trg[name][idx] = val

def _get_patch_action_constructor(enum: PatchOp) -> type:
    if enum == PatchOp.NEW_FIELD:
        return PatchAddKey
    elif enum == PatchOp.DEL_FIELD:
        return PatchDeleteKey
    elif enum == PatchOp.EDIT_FIELD:
        return PatchEditField
    elif enum == PatchOp.PATCH_ARRAY:
        return PatchArray
    else:
        raise RuntimeError(f'Unknown mapping for enum {enum}')

from json import loads, dumps

@dataclass
class Patch:
    actions: list[PatchAction]

    def __init__(self, actions: list[PatchAction]):
        self.actions = actions

    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return dumps(self.to_dict(), default=lambda x : str(x))
        
    @staticmethod
    def from_json(obj: str) -> Patch:
        return Patch.from_dict(loads(obj))
    
    @staticmethod
    def from_dict(obj: dict) -> Patch:
        actions = obj['actions']
        real_actions: list[PatchAction] = []
        for action in actions:
            op = action['op']
            if isinstance(op, str):
                op = PatchOp[action['op'].split('.')[1]]

            # op: str = action['op'].split('.')[1]
            
            del action['op']
            # print(f'OP: {op}')
            real_actions.append(_get_patch_action_constructor(op)(**action))
        return Patch(real_actions)



    def apply_inplace(self, target: dict):
        for action in self.actions:
            action.apply(target)


def _form_path(path: list[str], key: str):
    return '.'.join(path + [ key ])


def _generate_array_parch(
    path: str,
    source: list[Any],
    target: list[Any]
) -> PatchArray:
    end: int = len(target)
    sets: dict[int, Any] = {}
    for i in range(end):
        if source[i] != target[i]:
            sets[i] = target[i]
    return PatchArray(path, end, sets)
 
def _generate_dict_path_recursive(
    source: dict,
    new: dict,
    path: list[str],
    output: list[PatchAction]
):
    for k, v in new.items():
        if k not in source:
            # Case 1: We have a new key.
            output.append(PatchAddKey(_form_path(path, k), v))
        else:
            # Case 2: The key is mirrored.
            if isinstance(source[k], dict) and isinstance(v, dict):
                # Case 2A: They are both dictionaries, so we 
                # recurse down that path.
                _generate_dict_path_recursive(source[k], v, path + [ k ], output)
            elif isinstance(source[k], list) and isinstance(v, list):
                # Case 2B: They are both lists, so we need to diff them.
                # print(f'source[k] = {source[k]}, v = {v}')
                output.append(_generate_array_parch(_form_path(path, k), source[k], v))
            else:
                # Case 2C: We are just editing the field.
                output.append(PatchEditField(_form_path(path, k), v))

    for k, v in source.items():
        if k not in new:
            # Add a delete key action.
            output.append(PatchDeleteKey(_form_path(path, k)))


def generate_patch(source: dict, new: dict) -> Patch:
    output: list[PatchAction] = []
    _generate_dict_path_recursive(source, new, [], output)
    return Patch(output)
