## test script used to see if connection works - this can be deleted later


import asyncio
import sys
import os
import json
import uuid
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from replication.replication_manager import ReplicationManager
from backend.capital.server import CapitalNode
from backend.regional.standard_region_node import StandardRegionNode
from backend.regional.urban_region_node import UrbanRegionNode

def main():
    print("Starting up setup...")
    capital = CapitalNode(network_name="Capital", address=('127.0.0.1', 3042))

    alberta = StandardRegionNode(region_name="Carstairs", address=('127.0.0.1', 3051), capital_address=('127.0.0.1', 3042), interval_ms=2000)
    calgary = UrbanRegionNode(region_name="Calgary", address=('127.0.0.1', 3052), capital_address=('127.0.0.1', 3042), interval_ms=2000)

    rm = ReplicationManager(
        manager_id=1,
        capital_address=('127.0.0.1', 3042),
        address=('127.0.0.1', 4001)
    )

    rm._start()
    
    try:
        while True:
            alberta.tick_and_send()
            calgary.tick_and_send()

            time.sleep(1)
            
    except KeyboardInterrupt:
        capital.shutdown()
        alberta.shutdown()
        calgary.shutdown()
        rm.shutdown()
        # capital2.shutdown()

if __name__ == "__main__":
    main()