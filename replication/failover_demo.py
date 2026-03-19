import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.capital.server import CapitalNode
from backend.regional.standard_region_node import StandardRegionNode
from backend.regional.urban_region_node import UrbanRegionNode
from replication.replication_manager import ReplicationManager


def start_replica(manager_id: int, port: int):
    rm = ReplicationManager(
        manager_id=manager_id,
        capital_address=("127.0.0.1", 3042),
        address=("127.0.0.1", port),
    )
    rm._start()
    print(f"[demo] replica rm-{manager_id} started on ws://localhost:{port}")
    return rm


def stop_replica(manager_id: int, replicas: dict[int, ReplicationManager]):
    rm = replicas.pop(manager_id, None)
    if rm is None:
        return
    rm.shutdown()
    print(f"[demo] replica rm-{manager_id} stopped")


def main():
    print("[demo] starting capital + regions + replicas")
    print("[demo] open frontend and watch 'via localhost:PORT' as failover occurs")

    capital = CapitalNode(network_name="Capital", address=("127.0.0.1", 3042))
    carstairs = StandardRegionNode(
        region_name="Carstairs",
        address=("127.0.0.1", 3051),
        capital_address=("127.0.0.1", 3042),
        interval_ms=2000,
    )
    calgary = UrbanRegionNode(
        region_name="Calgary",
        address=("127.0.0.1", 3052),
        capital_address=("127.0.0.1", 3042),
        interval_ms=2000,
    )

    replica_ports = {1: 4001, 2: 4002, 3: 4003}
    replicas: dict[int, ReplicationManager] = {
        rid: start_replica(rid, port) for rid, port in replica_ports.items()
    }

    # Timed failover events
    timeline = [
        (10, "down", 1),
        (20, "up", 1),
        (30, "down", 2),
        (40, "down", 1),
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
                        replicas[manager_id] = start_replica(manager_id, replica_ports[manager_id])
                    event_index += 1

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
