import unittest

from ..common.components.plugins.leader_elec.bully_state_machine import BullyPacket, BullyElectionNode, BullyElectionHook, BullyPeer

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
    

if __name__ == "__main__":
    unittest.main()