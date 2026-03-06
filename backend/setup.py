from .capital.server import CapitalNode
from .regional.standard_region_node import StandardRegionNode
from .regional.urban_region_node import UrbanRegionNode
import time

if __name__ == "__main__":
    print("Starting up setup...")
    capital = CapitalNode(network_name="Capital", address=('127.0.0.1', 3042))

    alberta = StandardRegionNode(region_name="Alberta", address=('127.0.0.1', 3051), capital_address=('127.0.0.1', 3042), interval_ms=2000)
    calgary = UrbanRegionNode(region_name="Calgary", address=('127.0.0.1', 3052), capital_address=('127.0.0.1', 3042), interval_ms=2000)
    print("Regions connected. Testing api.hello:")
    
    capital2 = CapitalNode(network_name="Capital2", address=('127.0.0.1', 3043))
    capital2.connect(('127.0.0.1', 3042))
    
    print(capital2.send_message(target='Capital', method='api.hello', body={}))
    print("LINKED")
    
    try:
        while True:
            alberta.tick_and_send()
            calgary.tick_and_send()

            nat = capital2.send_message(target="Capital", method="api.national_infrastructure", body={})
            print("National:", nat)

            time.sleep(2.0)
    except KeyboardInterrupt:
        capital.shutdown()
        capital2.shutdown()