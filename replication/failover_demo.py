import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.capital.server import CapitalNode
from backend.regional.standard_region_node import StandardRegionNode
from backend.regional.urban_region_node import UrbanRegionNode
from backend.replication.replication_manager import ReplicationManager


def start_replica(manager_id: int, port: int) -> CapitalNode:
    rm = CapitalNode(
        network_name=f'rm_{manager_id}',
        leader_address=("127.0.0.1", 3042),
        address=("127.0.0.1", port),
        replica=True,
        leader_name='rm_0'
    )
    # rm._start()
    print(f"[demo] replica rm-{manager_id} started on ws://localhost:{port}")
    return rm


def stop_replica(manager_id: int, replicas: dict[int, CapitalNode]):
    rm = replicas.pop(manager_id, None)
    if rm is None:
        return
    rm.shutdown()
    print(f"[demo] replica rm-{manager_id} stopped")


def main():
    print("[demo] starting capital + regions + replicas")
    print("[demo] open frontend and watch 'via localhost:PORT' as failover occurs")

    capital = CapitalNode(network_name="rm_0", leader_address=None, leader_name=None, address=("127.0.0.1", 3042))
    carstairs = StandardRegionNode(
        region_name="Carstairs",
        address=("127.0.0.1", 3051),
        capital_address=("127.0.0.1", 3042),
        interval_ms=5000,
        capital_name='rm_0'
    )
    calgary = UrbanRegionNode(
        region_name="Calgary",
        address=("127.0.0.1", 3052),
        capital_address=("127.0.0.1", 3042),
        interval_ms=5000,
        capital_name='rm_0'
    )

    replica_ports = {1: 4003, 2: 4004, 3: 4005, 4: 4006, 5: 4007, 6: 4008}
    replicas: dict[int, CapitalNode] = {
        rid: start_replica(rid, port) for rid, port in replica_ports.items()
    }

    # Timed failover events
    timeline = [
        (5, "down", 1),
        (15, "up", 1),
        (16, "down", 2),
        (20, "down", 1),
        (25, "up", 2),
        (26, "down", 2),
        (30, "up", 2)
    ]
    # timeline = []

    start_time = time.time()
    event_index = 0

    try:
        while True:
            carstairs.tick_and_send()
            calgary.tick_and_send()

            elapsed = int(time.time() - start_time)
            if event_index < len(timeline):
                trigger_second, action, manager_id = timeline[event_index]
                if elapsed >= trigger_second:
                    if action == "down":
                        stop_replica(manager_id, replicas)
                    elif action == "up" and manager_id not in replicas:
                        replicas[manager_id] = start_replica(manager_id, replica_ports[manager_id])
                    event_index += 1
                    # print(f'Hello {event_index}')
            else:
                start_time = time.time()
                event_index = 0
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[demo] shutting down")
    finally:
        for manager_id in list(replicas.keys()):
            stop_replica(manager_id, replicas)

        calgary.shutdown()
        carstairs.shutdown()
        capital.shutdown()


if __name__ == "__main__":
    main()
