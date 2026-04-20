import json
import os
import signal
import sys
import threading
import time

from colorama import Fore

from backend.common.components.storage.memory import MemoryStorageBackend
from backend.common.components.util import NetworkAddress, NetworkEntry
from backend.implementation.capital.server import CapitalNode


def parse_entry(raw: dict) -> NetworkEntry:
    return NetworkEntry(
        name=raw["name"],
        address=NetworkAddress(
            ip=raw["address"]["ip"],
            port=raw["address"]["port"],
        ),
    )


def load_config() -> dict:
    path = os.environ.get("NODE_CONFIG_PATH")
    if not path and len(sys.argv) > 1:
        path = sys.argv[1]

    if not path:
        raise RuntimeError("Missing NODE_CONFIG_PATH or config path argument")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print('NEW VERSION')
    backend = MemoryStorageBackend()
    while True:
        cfg = load_config()
        print(f'Starting capital with config {cfg}')

        entry = parse_entry(cfg["entry"])
        peers = [parse_entry(x) for x in cfg["peers"]]

        node = CapitalNode(
            capital_name=cfg["capital_name"],
            entry=entry,
            peers=peers,
            backend=backend
        )

        print(f'Capital Entry: {entry}')

        stop_event = threading.Event()

        def handle_shutdown(_sig, _frame):
            print(f"[runner:{entry.name}] shutting down")
            try:
                node.shutdown()
            finally:
                stop_event.set()

        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)

        print(f"[runner:{entry.name}] started")
        while not stop_event.is_set():
            sim_down = node.is_sim_down()
            if sim_down is not None:
                print(f'{Fore.RED}[SIMULATION] Detected down request for {sim_down}ms{Fore.RESET}')
                node.shutdown()
                break
            time.sleep(1)
            # print(f'Hello')
        if stop_event.is_set():
            break
        time.sleep(sim_down / 1000.0)


if __name__ == "__main__":
    main()