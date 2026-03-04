# Regional node
import argparse
import random
import time
import requests

DEFAULT_CAPITAL = "http://localhost:5000"

def build_state():
    """
    Demo 2: simple synthetic state.
    Later: replace with aggregation over infrastructure site objects.
    """
    power = random.choice(["stable", "unstable"])
    transport = random.choice(["operational", "degraded", "down"])

    # keep these realistic: 0..100
    medical_capacity = random.randint(40, 100)
    water_capacity = random.randint(50, 100)
    fuel_storage = random.randint(30, 100)

    return {
        "power": power,
        "medical_capacity": medical_capacity,
        "transport": transport,
        "water_capacity": water_capacity,
        "fuel_storage": fuel_storage,
    }

def post_update(capital_url: str, name: str, state: dict):
    payload = {"name": name, "state": state}
    r = requests.post(f"{capital_url}/api/update_state", json=payload, timeout=3)
    r.raise_for_status()
    return r.json()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Unique region name, e.g. Alberta")
    parser.add_argument("--capital", default=DEFAULT_CAPITAL, help="Capital base URL, e.g. http://localhost:5000")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between updates")
    args = parser.parse_args()

    if args.name.strip().lower() == "capital":
        raise SystemExit("Region name cannot be 'Capital' (reserved). Choose a different name.")

    print(f"[regional] starting node name={args.name} capital={args.capital} interval={args.interval}s")

    while True:
        state = build_state()
        try:
            resp = post_update(args.capital, args.name, state)
            print(f"[regional:{args.name}] posted update -> {resp}")
        except Exception as e:
            print(f"[regional:{args.name}] failed to post update: {e}")
        time.sleep(args.interval)

if __name__ == "__main__":
    main()