import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.regional.standard_region_node import StandardRegionNode
from backend.regional.urban_region_node import UrbanRegionNode
from backend.replication.replication_manager import ReplicationManager


def start_replica(manager_id: int, port: int, peer_addresses: dict[int, tuple[str, int]]):
    rm = ReplicationManager(
        manager_id=manager_id,
        peer_addresses=peer_addresses,
        address=("127.0.0.1", port),
    )
    print(f"[demo] replica rm-{manager_id} started on ws://localhost:{port}")
    return rm


def stop_replica(manager_id: int, replicas: dict[int, ReplicationManager]):
    rm = replicas.pop(manager_id, None)
    if rm is None:
        return
    rm.shutdown()
    print(f"[demo] replica rm-{manager_id} stopped")


def main():
    replica_ports = {
        1: 4001,
        2: 4002,
        3: 4003,
        4: 4004,
    }
    peer_addresses = {rid: ("127.0.0.1", port) for rid, port in replica_ports.items()}

    print("[demo] starting replicas")
    replicas: dict[int, ReplicationManager] = {
        rid: start_replica(rid, port, peer_addresses)
        for rid, port in replica_ports.items()
    }

    time.sleep(2)

    for rm in replicas.values():
        rm._start()

    time.sleep(2)

    for rm in replicas.values():
        rm.start_election()

    capital_candidates = list(peer_addresses.values())

    print("[demo] starting regions")
    carstairs = StandardRegionNode(
        region_name="Carstairs",
        address=("127.0.0.1", 3051),
        capital_candidates=capital_candidates,
        interval_ms=2000,
    )
    calgary = UrbanRegionNode(
        region_name="Calgary",
        address=("127.0.0.1", 3052),
        capital_candidates=capital_candidates,
        interval_ms=2000,
    )

    timeline = [
        (8, "down", 4),   # kill the highest-ID leader
        (18, "up", 4),    # bring it back
        (28, "down", 3),  # kill next likely leader
        (38, "up", 3),
        (48, "down",2),
        (58, "up", 2),
    ]

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
                        replicas[manager_id] = start_replica(manager_id, replica_ports[manager_id], peer_addresses)
                        time.sleep(1)
                    event_index += 1

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[demo] shutting down")
    finally:
        for manager_id in list(replicas.keys()):
            stop_replica(manager_id, replicas)

        calgary.shutdown()
        carstairs.shutdown()


if __name__ == "__main__":
    main()