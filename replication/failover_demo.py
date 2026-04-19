import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.implementation.capital.server import CapitalNode
from backend.implementation.regional.standard_region_node import StandardRegionNode
from backend.implementation.regional.urban_region_node import UrbanRegionNode
from backend.common.node.common.sync.mdns import DnsEntry


def start_capital_replica(replica_id: int, port: int, peer_addresses):
    node = CapitalNode(
        network_name=f"rm-{replica_id}",
        address=("127.0.0.1", port),
        peer_addresses=peer_addresses,
        seed_leader_name=None,
        bootstrap_leader=False,
    )
    print(f"[demo] replica rm-{replica_id} started on ws://localhost:{port}")
    return node


def stop_capital_replica(replica_id: int, replicas: dict[int, CapitalNode]):
    node = replicas.pop(replica_id, None)
    if node is None:
        return
    node.shutdown()
    print(f"[demo] replica rm-{replica_id} stopped")


def start_region_replica(
    region_type: str,
    logical_name: str,
    replica_name: str,
    port: int,
    capital_candidates,
    replica_peer_addresses,
):
    cls = StandardRegionNode if region_type == "standard" else UrbanRegionNode

    region = cls(
        region_name=logical_name,
        network_name=replica_name,
        address=("127.0.0.1", port),
        capital_candidates=capital_candidates,
        interval_ms=2000,
        replica_peer_addresses=replica_peer_addresses,
    )

    if hasattr(region, "restore_from_capital"):
        region.restore_from_capital()

    print(f"[demo] region replica {replica_name} ({logical_name}) started on ws://localhost:{port}")
    return region


def stop_region_replica(replica_name: str, regions: dict[str, object]):
    region = regions.pop(replica_name, None)
    if region is None:
        return
    region.shutdown()
    print(f"[demo] region replica {replica_name} stopped")


def tick_regions(regions: dict[str, object]):
    for region in list(regions.values()):
        try:
            region.tick_and_send()
        except Exception as e:
            print(f"[demo] region tick failed for {getattr(region, 'network_name', 'unknown')}: {e}")


def main():
    print("[demo] starting capital replica cluster + regions")

    replica_ports = {
        1: 4001,
        2: 4002
    }

    peer_addresses = [
        (f"rm-{rid}", "127.0.0.1", port)
        for rid, port in replica_ports.items()
    ]

    region_replica_specs = {
        "Carstairs": {
            "type": "standard",
            "replicas": {
                "Carstairs-r1": 3051,
                "Carstairs-r2": 3052,
                # "Carstairs-r3": 3053,
            },
        },
    }

    replicas: dict[int, CapitalNode] = {
        rid: start_capital_replica(rid, port, peer_addresses)
        for rid, port in replica_ports.items()
    }

    full_capital_entries = [
        DnsEntry(name=f"rm-{rid}", ip="127.0.0.1", port=port)
        for rid, port in replica_ports.items()
    ]

    time.sleep(2)

    print("[demo] starting region replicas")
    regions: dict[str, object] = {}

    for logical_name, spec in region_replica_specs.items():
        replica_peer_addresses = [
            (replica_name, "127.0.0.1", port)
            for replica_name, port in spec["replicas"].items()
        ]

        for replica_name, port in spec["replicas"].items():
            regions[replica_name] = start_region_replica(
                region_type=spec["type"],
                logical_name=logical_name,
                replica_name=replica_name,
                port=port,
                capital_candidates=full_capital_entries,
                replica_peer_addresses=replica_peer_addresses,
            )

    timeline = [
        (6, "replica_down", 3),
        (20, "replica_up", 3),
        (30, "region_replica_down", "Carstairs-r3"),
        (45, "region_replica_up", "Carstairs-r3"),
    ]
    timeline = []

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
                        stop_capital_replica(target, replicas)

                    elif action == "replica_up" and target not in replicas:
                        replicas[target] = start_capital_replica(
                            target,
                            replica_ports[target],
                            peer_addresses,
                        )
                        time.sleep(2)

                    elif action == "region_replica_down":
                        stop_region_replica(target, regions)

                    elif action == "region_replica_up" and target not in regions:
                        logical_name = target.split("-r")[0]
                        spec = region_replica_specs[logical_name]
                        port = spec["replicas"][target]
                        replica_peer_addresses = [
                            (replica_name, "127.0.0.1", p)
                            for replica_name, p in spec["replicas"].items()
                        ]

                        regions[target] = start_region_replica(
                            region_type=spec["type"],
                            logical_name=logical_name,
                            replica_name=target,
                            port=port,
                            capital_candidates=full_capital_entries,
                            replica_peer_addresses=replica_peer_addresses,
                        )
                        time.sleep(2)

                    else:
                        print(f"[demo] unhandled timeline action: {action} target={target}")

                    event_index += 1

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[demo] shutting down")
    finally:
        for replica_id in list(replicas.keys()):
            stop_capital_replica(replica_id, replicas)

        for replica_name in list(regions.keys()):
            stop_region_replica(replica_name, regions)


if __name__ == "__main__":
    main()