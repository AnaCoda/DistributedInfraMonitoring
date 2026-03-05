from .capital.server import CapitalNode
import time

if __name__ == "__main__":
    print("Starting up setup...")
    capital = CapitalNode(network_name="Capital", address=('127.0.0.1', 3042))
    
    capital2 = CapitalNode(network_name="Capital2", address=('127.0.0.1', 3043))
    capital2.connect(('127.0.0.1', 3042))
    
    print(capital2.send_message(target='Capital', method='api.hello', body={}))
    print("LINKED")
    
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        capital.shutdown()
        capital2.shutdown()