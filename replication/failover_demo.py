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


def start_region(region_type: str, name: str, port: int, capital_candidates):
    if region_type == "standard":
        region = StandardRegionNode(
            region_name=name,
            address=("127.0.0.1", port),
            capital_candidates=capital_candidates,
            interval_ms=2000,
        )
    else:
        region = UrbanRegionNode(
            region_name=name,
            address=("127.0.0.1", port),
            capital_candidates=capital_candidates,
            interval_ms=2000,
        )

    print(f"[demo] region {name} started on ws://localhost:{port}")
    return region


def stop_region(region_name: str, regions: dict[str, object]):
    region = regions.pop(region_name, None)
    if region is None:
        return
    region.shutdown()
    print(f"[demo] region {region_name} stopped")


def tick_regions(regions: dict[str, object]):
    for region in list(regions.values()):
        try:
            region.tick_and_send()
        except Exception as e:
            print(f"[demo] region tick failed for {getattr(region, 'region_name', 'unknown')}: {e}")


def main():
    replica_ports = {
        1: 4001,
        2: 4002,
        3: 4003,
        4: 4004,
    }
    peer_addresses = {rid: ("127.0.0.1", port) for rid, port in replica_ports.items()}
    capital_candidates = list(peer_addresses.values())

    region_specs = {
        "Carstairs": {"type": "standard", "port": 3051},
        "Calgary": {"type": "urban", "port": 3052},
    }

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

    print("[demo] starting regions")
    regions: dict[str, object] = {
        name: start_region(spec["type"], name, spec["port"], capital_candidates)
        for name, spec in region_specs.items()
    }

    timeline = [
        # Replica / capital failover
        (8, "replica_down", 4),
        (18, "replica_up", 4),
        (28, "replica_down", 3),
        (38, "replica_up", 3),

        # Regional failure / recovery
        (48, "region_down", "Calgary"),
        (58, "region_up", "Calgary"),

        # Another replica failure / recovery
        (68, "replica_down", 2),
        (78, "replica_up", 2),
    ]

    start_time = time.time()
    event_index = 0

    try:
        while True:
            tick_regions(regions)

            elapsed = int(time.time() - start_time)
            if event_index < len(timeline):
                trigger_second, action, target = timeline[event_index]
                if elapsed >= trigger_second:
                    if action == "replica_down":
                        stop_replica(target, replicas)

                    elif action == "replica_up" and target not in replicas:
                        replicas[target] = start_replica(target, replica_ports[target], peer_addresses)
                        time.sleep(1)
                        replicas[target]._start()

                    elif action == "region_down":
                        stop_region(target, regions)

                    elif action == "region_up" and target not in regions:
                        time.sleep(3) # Avoid crash on existing infra nodes
                        spec = region_specs[target]
                        regions[target] = start_region(
                            spec["type"],
                            target,
                            spec["port"],
                            capital_candidates,
                        )

                    event_index += 1

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[demo] shutting down")
    finally:
        for manager_id in list(replicas.keys()):
            stop_replica(manager_id, replicas)

        for region_name in list(regions.keys()):
            stop_region(region_name, regions)


if __name__ == "__main__":
    main()