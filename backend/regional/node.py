# backend/regional/node.py
import argparse
import time

from .standard_region_node import StandardRegionNode
from .urban_region_node import UrbanRegionNode

NODE_TYPES = {"standard": StandardRegionNode, "urban": UrbanRegionNode}

DEFAULT_CAPITAL_HOST = "127.0.0.1"
DEFAULT_CAPITAL_PORT = 6000

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--type", default="standard", choices=NODE_TYPES.keys())
    p.add_argument("--interval", type=float, default=2.0, help="Seconds between heartbeats")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, required=True, help="This node's TCP listen port (unique per node)")
    p.add_argument("--capital-host", default=DEFAULT_CAPITAL_HOST)
    p.add_argument("--capital-port", type=int, default=DEFAULT_CAPITAL_PORT)
    args = p.parse_args()

    interval_ms = int(args.interval * 1000)

    node_cls = NODE_TYPES[args.type]
    node = node_cls(
        region_name=args.name,
        address=(args.host, args.port),
        capital_address=(args.capital_host, args.capital_port),
        interval_ms=interval_ms,
    )

    try:
        while True:
            node.tick_and_send()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        node.shutdown()

if __name__ == "__main__":
    main()