import unittest
from copy import deepcopy
# from ..common.dictutil import merge_dictionaries
from ..common.node.common.patching.patch import Patch
from ..common.node.common.patching.mpatch import VersionedPatch, ManagedState
from ..common.node.common.storage.memory import MemoryStorageBackend
from ..common.node.common.rep_log.log import ReplicationLog, Operation

class DictUtils(unittest.TestCase):

    # def test_merge(self):
    #     source = { "good": "morning", "people": { "homer": 1 } }
    #     new = { "bad": "day", "people": { "seth": 2 } }
    #     merge_dictionaries(source, new)
    #     self.assertEqual(source, {'good': 'morning', 'people': {'homer': 1, 'seth': 2}, 'bad': 'day'})

    # def test_diff(self):
    #     original = { "version": 1, "hello": "fortran", "people": { "homer": 1 }, "sources": [1, 2] }
    #     updated = { "version": 2, "people": { "homer": 2, "seth": 3 }, "gamer": 4, "sources": [ 1, 3 ]}
    #     patch = Patch.diff(original, updated)
 
    #     patch = Patch.from_json(patch.to_json())
    #     patch = Patch.from_dict(patch.to_dict())


    #     patch.apply_inplace(original)
    #     self.assertEqual(original, updated)

    def test_replication_log(self):
        backend = MemoryStorageBackend()
        log = ReplicationLog(backend)

        self.assertEqual(log.get_sequence_pos(), 0)
        self.assertEqual(len(log.retrieve_all_logs()), 0)

        log.add_log(Operation(1, { 'hello': 4 }))

        self.assertEqual(log.get_sequence_pos(), 1)
        self.assertEqual(len(log.retrieve_all_logs()), 1)
        
        log = ReplicationLog(backend)
        self.assertEqual(log.get_sequence_pos(), 1)


    def test_memory_backend(self):
        backend = MemoryStorageBackend()
        self.assertEqual(backend.read('hello', 'world'), None)
        backend.write('hello', 'world', 2)
        self.assertEqual(backend.read('hello', 'world'), 2)

    def test_diff_array_longer(self):
        original = { "items": [1, 2] }
        updated = { "items": [1, 2, 3] }
        patch = Patch.diff(original, updated)


        patch.apply_inplace(original)
        self.assertEqual(original, updated)

    def test_diff_array_shorter(self):
        original = { "items": [1, 2, 3] }
        updated = { "items": [1, 2] }
        patch = Patch.diff(original, updated)


        patch.apply_inplace(original)
        self.assertEqual(original, updated)

    def test_invert_patch(self):
        original = { "version": 1, "hello": "fortran", "people": { "homer": 1 }, "sources": [1, 2] }
        updated = { "version": 2, "people": { "homer": 2, "seth": 3 }, "gamer": 4, "sources": [ 1, 3 ]}
        patch = Patch.diff(original, updated)

        true_original = deepcopy(original)

        rewind = patch.apply_inplace(original, get_rewind=True)
        self.assertEqual(original, updated)
        
        rewind.apply_inplace(original)
        self.assertEqual(original, true_original)

    def test_invert_patch_array_longer(self):
        original = { "items": [1, 2, 3] }
        updated = { "items": [1, 2] }
        patch = Patch.diff(original, updated)

        true_original = deepcopy(original)

        rewind = patch.apply_inplace(original, get_rewind=True)
        self.assertEqual(original, updated)
        
        rewind.apply_inplace(original)
        self.assertEqual(original, true_original)

    def test_invert_patch_array_shorter(self):
        original = { "items": [1, 2] }
        updated = { "items": [1, 2, 3] }
        patch = Patch.diff(original, updated)

        true_original = deepcopy(original)

        rewind = patch.apply_inplace(original, get_rewind=True)
        self.assertEqual(original, updated)
        
        rewind.apply_inplace(original)
        self.assertEqual(original, true_original)

    def test_versioned_patches(self):

        p1 = { "ping": 1, "hello": "world" }
        p2 = { "ping": 2 }
        p3 = { "ping": 3, "hello": "fortran" }
        p4 = { "ping": 4, "john": "yes"}



        passes = list(multiplex_patches(
            VersionedPatch.diff(2, p1, p2),
            VersionedPatch.diff(3, p2, p3),
            VersionedPatch.diff(4, p3, p4)
        ))

        for instance in reversed(passes):
            # We start the managed state at version=1.
            ms = ManagedState.from_dict(1, p1)
            for item in instance:
                ms.apply_update(item)
            self.assertEqual(ms.inspect_dict(), p4, f'Had update order = {instance} but resulting dictionary not equal to P3.')




import itertools

def multiplex_patches(*args):
    for pair in itertools.permutations(args, r=len(args)):
        yield list(pair)
    

if __name__ == "__main__":
    unittest.main()