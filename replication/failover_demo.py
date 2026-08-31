import os
import sys
import time
from typing import List

from colorama import Fore

from backend.implementation.regional.base import RegionalNode

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.common.components.util import NetworkAddress, NetworkEntry
from backend.implementation.capital.server import CapitalNode


def start_capital_replica(
    entry: NetworkEntry,
    peers: List[NetworkEntry],
):
    node = CapitalNode(
        entry.name.split('-')[0],
        entry,
        peers
    )
    print(f"[demo] replica {entry.name} started.")
    return node


def stop_capital_replica(replica_id: int, replicas: dict[int, CapitalNode]):
    node = replicas.pop(replica_id, None)
    if node is None:
        return
    node.shutdown()
    print(f"[demo] replica rm-{replica_id} stopped")


def start_region_replica(
    region_type: str,
    entry: NetworkEntry,
    peers: List[NetworkEntry],
    capitals: List[NetworkEntry]
    # logical_name: str,
    # replica_name: str,
    # port: int,
    # capital_candidates,
    # replica_peer_addresses,
):

    region = RegionalNode(
        region_name=entry.name.split('-')[0],
        entry=entry,
        capital_addresses=capitals,
        peers=peers
    )

    if hasattr(region, "restore_from_capital"):
        region.restore_from_capital()

    print(f"[demo] region replica {entry.name} started.")
    return region


def stop_region_replica(replica_name: str, regions: dict[str, object]):
    region = regions.pop(replica_name, None)
    if region is None:
        return
    region.shutdown()
    print(f"[demo] region replica {replica_name} stopped")


# def tick_regions(regions: dict[str, object]):
#     for region in list(regions.values()):
#         # try:
#             # region.tick_and_send()
#         # except Exception as e:
#             # print(f"[demo] region tick failed for {getattr(region, 'network_name', 'unknown')}: {e}")
from backend.implementation.infrastructure.hospital import Hospital

def main():
    print("[demo] starting capital replica cluster + regions")

    replica_ports = {
        1: 4001,
        2: 4002,
        3: 4003
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

    # from ...
    # infra = Hospital('Hospital-1', [
    #     NetworkEntry(name='Carstairs-r1', address=NetworkAddress(ip='127.0.0.1', port=3051)),
    #     NetworkEntry(name='Carstairs-r2', address=NetworkAddress(ip='127.0.0.1', port=3052))
    # ])
    # print(f'Infra Launched On: {infra._get_net_addr()}')

    full_capital_entries = [
        NetworkEntry(name=f'rm-{rid}', address=NetworkAddress(ip='127.0.0.1', port=port))
        # DnsEntry(name=f"rm-{rid}", ip="127.0.0.1", port=port)
        for rid, port in replica_ports.items()
    ]

    replicas: dict[int, CapitalNode] = {
        rid: start_capital_replica(
            entry=NetworkEntry(name=f'rm-{rid}', address=NetworkAddress(ip='127.0.0.1', port=port)),
            peers=full_capital_entries
        )
        for rid, port in replica_ports.items()
    }

    

    time.sleep(2)

    print("[demo] starting region replicas")
    regions: dict[str, object] = {}

    for logical_name, spec in region_replica_specs.items():
        replica_peer_addresses = [
            NetworkEntry(name=replica_name, address=NetworkAddress(ip='127.0.0.1', port=port))
            for replica_name, port in spec["replicas"].items()
        ]

        for replica_name, port in spec["replicas"].items():
            entry: NetworkEntry = NetworkEntry(name=replica_name, address=NetworkAddress(ip='127.0.0.1', port=port))
        
            regions[replica_name] = start_region_replica(
                region_type=spec["type"],
                entry=entry,
                peers=replica_peer_addresses,
                capitals=list(full_capital_entries)

            )

    # timeline = [
    #     (6, "replica_down", 3),
    #     (20, "replica_up", 3),
    #     (30, "region_replica_down", "Carstairs-r3"),
    #     (45, "region_replica_up", "Carstairs-r3"),
    # ]
    timeline = [
        (6, "replica_down", 2),
        (25, "replica_up", 2)
    ]
    timeline = []

    start_time = time.time()
    event_index = 0

    count = 0

    try:
        while True:
            # tick_regions(regions)

            elapsed = int(time.time() - start_time)
            if event_index < len(timeline):
                trigger_second, action, target = timeline[event_index]
                if elapsed >= trigger_second:
                    print(f'[Simulation] {Fore.CYAN}Executing action={action} towards target={target}{Fore.RESET}')
                    if action == "replica_down":
                        stop_capital_replica(target, replicas)

                    elif action == "replica_up" and target not in replicas:
                        replicas[target] = start_capital_replica(
                            entry=NetworkEntry(
                                name=f'rm-{target}',
                                address=NetworkAddress(ip='127.0.0.1', port=replica_ports[target])
                            ),
                            peers=full_capital_entries
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
                    
            count += 1
            time.sleep(1)
            # if count % 5 == 0:
                # infra.update_value()
            print(f'Event Idx: {count}')

    except KeyboardInterrupt:
        print("\n[demo] shutting down")
    finally:
        for replica_id in list(replicas.keys()):
            stop_capital_replica(replica_id, replicas)
        print(f'Capitals down.')

        for replica_name in list(regions.keys()):
            stop_region_replica(replica_name, regions)
        print(f'Regions down.')

        # infra.shutdown()
        print(f'Infra')

if __name__ == "__main__":
    main()