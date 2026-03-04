import argparse

from .standard_region_node import StandardRegionNode
from .urban_region_node import UrbanRegionNode


DEFAULT_CAPITAL = "http://localhost:5000"

NODE_TYPES = {
    "standard": StandardRegionNode,
    "urban": UrbanRegionNode,
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Unique region name, e.g. Alberta")
    parser.add_argument("--type", default="standard", choices=NODE_TYPES.keys(), help="Region type")
    parser.add_argument("--capital", default=DEFAULT_CAPITAL, help="Capital base URL, e.g. http://localhost:5000")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between heartbeats")
    args = parser.parse_args()

    node_cls = NODE_TYPES[args.type]
    node = node_cls(region_name=args.name, capital_url=args.capital, interval_s=args.interval)
    node.run_forever()


if __name__ == "__main__":
    main()