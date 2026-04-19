import unittest
from copy import deepcopy
from dataclasses import asdict
# from ..common.dictutil import merge_dictionaries
# from ..common.node.common.patching.patch import Patch
# from ..common.node.common.patching.mpatch import VersionedPatch, ManagedState
from ..common.components.storage.memory import MemoryStorageBackend
from ..common.components.rep_log.log import ReplicationLog, Operation
from ..common.components.plugins.replication.rep_state_machine import ReplicationStateMachine, ReplicationStateMachineState, ReplicationOp, ReplicationMsg

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

    def test_replication_state_machine_init(self):
        sm = ReplicationStateMachine('dummy', MemoryStorageBackend())
        # print(sm.poll())
        sm.set_leader('jeff')
        polled = sm.poll()
        self.assertEqual(len(polled), 1)
        self.assertEqual(polled[0].op, ReplicationOp.SYNC_REQUEST)
        self.assertEqual(polled[0].body['sequence'], 0)

    def test_replication_state_machine_syncup(self):
        sm = ReplicationStateMachine('dummy', MemoryStorageBackend())
        
        sm.set_leader('jeff')

        # Poll is not necessary but will help.
        sm.poll()


        sm.receive(ReplicationMsg.from_op(
            op=ReplicationOp.SYNC_RESPONSE,
            body={ 'logs': [ asdict(Operation(1, { 'hello': 4 })) ] }
        ))
      

        self.assertEqual(sm.replication_log.get_sequence_pos(), 1)
        # Now we should be in executing.

        result = sm.receive(ReplicationMsg.from_op(
            op=ReplicationOp.OPERATION,
            body=Operation(2, { 'hello': 4 })
        ))
        self.assertTrue(result, "The message should be handled.")


        # We should not be able to handle another operation concurrently.
        result = sm.receive(ReplicationMsg.from_op(
            op=ReplicationOp.OPERATION,
            body=Operation(2, { 'hello': 4 })
        ))
        self.assertFalse(result, "We should only be free to accept new operations once we commit.")

        self.assertFalse(
            expr=sm.receive(ReplicationMsg.from_op(
                op=ReplicationOp.COMMIT,
                body={ 'sequence': 1 }
            )),
            msg="We should NOT have been able to succesfully commit message with sequence number 1."
        )

        self.assertTrue(
            expr=sm.receive(ReplicationMsg.from_op(
                op=ReplicationOp.COMMIT,
                body={ 'sequence': 2 }
            )),
            msg="We should have been able to succesfully commit message with sequence number 2."
        )


    def test_replication_state_machine_behind(self):
        sm = ReplicationStateMachine('dummy', MemoryStorageBackend())
        
        sm.set_leader('jeff')

        # Poll is not necessary but will help.
        sm.poll()


        sm.receive(ReplicationMsg.from_op(
            op=ReplicationOp.SYNC_RESPONSE,
            body={ 'logs': [ asdict(Operation(1, { 'hello': 4 })) ] }
        ))
      

        self.assertEqual(sm.replication_log.get_sequence_pos(), 1)
        # Now we should be in executing.

        self.assertFalse(
            expr=sm.receive(ReplicationMsg.from_op(
                op=ReplicationOp.OPERATION,
                body=Operation(3, {})
            )),
            msg="We should have been able to succesfully commit message with sequence number 2."
        )

        polled = sm.poll()
        self.assertEqual(len(polled), 1)

        obj = polled[0]
        self.assertEqual(obj.op, ReplicationOp.REQUEST_MISSING)
        self.assertListEqual(obj.body['logs'], [2, 3])

 
        self.assertFalse(
            expr=sm.receive(ReplicationMsg.from_op(
                op=ReplicationOp.RESEND,
                body={ 'logs': [ asdict(Operation(2, {})) ]}
            )),
            msg="We did not resend the requested sequence."
        )
        self.assertTrue(
            expr=sm.receive(ReplicationMsg.from_op(
                op=ReplicationOp.RESEND,
                body={ 'logs': [ asdict(Operation(2, {})), asdict(Operation(3, {})) ]}
            )),
            msg="We resent the requested sequence."
        )

        self.assertEqual(sm.replication_log.get_sequence_pos(), 3)
        self.assertEqual(sm.get_state(), ReplicationStateMachineState.EXECUTING)

    
    def test_replication_sm_leader(self):

        sm = ReplicationStateMachine('jeff', MemoryStorageBackend())
        self.assertEqual(sm.get_state(), ReplicationStateMachineState.INIT)

        sm.set_leader('jeff')

        self.assertEqual(len(sm.poll()), 0)
        self.assertEqual(sm.get_state(), ReplicationStateMachineState.EXECUTING)

    def test_replication_sm_wait_for_leader(self):
        sm = ReplicationStateMachine('bob', MemoryStorageBackend())
        self.assertEqual(len(sm.poll()), 0)
        self.assertEqual(sm.get_state(), ReplicationStateMachineState.INIT)
        
        sm.set_leader('jeff')
        self.assertEqual(len(sm.poll()), 1)
        self.assertEqual(sm.get_state(), ReplicationStateMachineState.STARTED)


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

   



if __name__ == "__main__":
    unittest.main()