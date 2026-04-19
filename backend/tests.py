import unittest
from copy import deepcopy
from dataclasses import asdict

import unittest


from backend.common.components.plugins.leader_elec.bully_state_machine import BullyElectionHook, BullyElectionNode, BullyPeer
from backend.common.components.plugins.replication.rep_state_machine import ReplicationMsg, ReplicationOp, ReplicationStateMachine, ReplicationStateMachineState
from backend.common.components.rep_log.log import ReplicationLog
from backend.common.components.rep_log.operation import Operation
from backend.common.components.storage.memory import MemoryStorageBackend

class LeaderTests(unittest.TestCase):

    def test_election(self):
        clock = PseudoClock()
        pool = create_node_pool(n=3, clock=clock)
        outboxes = {}
        for i in range(100):
            tick_pool(outboxes, pool)
            clock.advance(1)
        # print(f'pool: {pool[0].get_leader()}')
        self.assertEqual(pool[0].get_leader().unique_id, 2)
        self.assertEqual(pool[1].get_leader().unique_id, 2)
        self.assertEqual(pool[2].get_leader().unique_id, 2)

    def test_bully_hooks(self):
        clock = PseudoClock()
        pool = create_node_pool(n=3, clock=clock)

        on_bc_leader = []

        pool[2].register_hook(BullyElectionHook.ON_BECOME_LEADER, lambda: on_bc_leader.append(pool[2].get_leader().unique_id))

        outboxes = {}
        for i in range(100):
            tick_pool(outboxes, pool)
            clock.advance(1)
        self.assertEqual(pool[0].get_leader().unique_id, 2)
        self.assertEqual(pool[1].get_leader().unique_id, 2)
        self.assertEqual(pool[2].get_leader().unique_id, 2)

        self.assertListEqual(on_bc_leader, [2])

    def test_crash_nonleader(self):
        clock = PseudoClock()
        pool = create_node_pool(n=3, clock=clock, verbose=False)
        outboxes = {}
        for i in range(40):
            tick_pool(outboxes, pool)
            clock.advance(1)

            if i == 15:
                pool.pop(1)
        self.assertEqual(pool[0].get_leader().unique_id, 2)
        self.assertEqual(pool[1].get_leader().unique_id, 2)

    def test_crash_leader(self):
        clock = PseudoClock()
        pool = create_node_pool(n=3, clock=clock, timeout=10.0, verbose=False)
        outboxes = {}
        for i in range(45):
            tick_pool(outboxes, pool)
            clock.advance(1)

            if i == 15:
                pool.pop(2)
        self.assertEqual(pool[0].get_leader().unique_id, 1)
        self.assertEqual(pool[1].get_leader().unique_id, 1)

    def test_crash_leader_n4_crash2(self):
        clock = PseudoClock()
        pool = create_node_pool(n=4, clock=clock, timeout=10.0, verbose=False)
        outboxes = {}
        for i in range(45):
            tick_pool(outboxes, pool)
            clock.advance(1)

            if i == 15:
                pool.pop(3)
                pool.pop(2)
        self.assertEqual(pool[0].get_leader().unique_id, 1)
        self.assertEqual(pool[1].get_leader().unique_id, 1)

    # def test_clock(self):
    #     clock = PseudoClock()
    #     pool = create_node_pool(n=3, clock=clock, timeout=10.0, verbose=True)
        
    #     pool2 = create_node_pool(n=3, clock=clock, timeout=10.0, verbose=True)
    #     outboxes = {}
    #     popped = None
    #     for i in range(45):
    #         tick_pool(outboxes, pool)
    #         clock.advance(1)

    #         if i == 15:
    #             # print("REMOVED")
    #             popped = pool.pop(1)
    #         if i == 25:
    #             # print("ADDED BACK")
    #             pool.insert(1, pool2[1])
    #             # pool.pop(2)
    #     self.assertEqual(pool[0].get_leader().unique_id, 1)
    #     self.assertEqual(pool[1].get_leader().unique_id, 1)




class PseudoClock:

    def __init__(self):
        self.time = 0
    
    def advance(self, delta: int):
        self.time += delta

    def get_time(self) -> float:
        # self.advance(1)
        return float(self.time)

def create_node_pool(n: int, clock: PseudoClock, timeout: float = 50.0, verbose: bool = False) -> list[BullyElectionNode]:
    peers = [ BullyPeer(f'n-{i}', i, i) for i in range(n) ]
    nodes = [ BullyElectionNode(peer, peers, get_time=clock.get_time, timeout=timeout, verbose=verbose) for peer in peers ]
    return nodes

def tick_pool(outboxes: dict, pool: list[BullyElectionNode]):
    # print(">> Start ticks")
    for node in pool:
        if node.node_info not in outboxes or len(outboxes[node.node_info]) == 0:
            node.receive(None)
        else:
            while outboxes[node.node_info]:
                # msg = outboxes[node.node_info].pop(0)
                msg = outboxes[node.node_info].pop(0)
                if node.verbose:
                    print(f'[{msg.source.name}] -> [{msg.destination.name}] | packet = {msg}')
                
                node.receive(msg)
        out_msgs = node.poll()
        if len(out_msgs) != 0 and node.verbose:
            print(f'Outbox for {node.node_info.name}:')
        for msg in out_msgs:
            if node.verbose and msg.type:
                print(f'  - {msg}')
            if msg.destination not in outboxes:
                outboxes[msg.destination] = []
            outboxes[msg.destination].append(msg)

import itertools

def multiplex_patches(*args):
    for pair in itertools.permutations(args, r=len(args)):
        yield list(pair)
    



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