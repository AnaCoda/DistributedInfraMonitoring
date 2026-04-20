from json import load
import os
import logging
import time

from colorama import Fore


from backend.common.components.storage.memory import MemoryStorageBackend
from backend.common.components.util import NetworkAddress, NetworkEntry
from backend.common.raw import RawNode
from backend.implementation.capital.server import CapitalNode
from backend.implementation.infrastructure.common import InfrastructureNode
from backend.implementation.regional.base import RegionalNode
from backend.runners.config import RunnerConfig
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format=f"{Fore.LIGHTBLACK_EX}%(asctime)s{Fore.RESET} {Fore.YELLOW}(%(levelname)s){Fore.RESET} %(message)s",
        handlers=[
            logging.StreamHandler()
        ]
    )

LOGGER = logging.getLogger(__name__)

def load_config(name: str) -> RunnerConfig:
    full_path: str = os.path.join('configs/fly', f'{name}.json')
    with open(full_path, 'r') as fi:
        return RunnerConfig.model_validate(load(fi))
    
def get_application_node(
    config: RunnerConfig
) -> CapitalNode | RegionalNode | InfrastructureNode:
    if config.variant == 'capital':
        return CapitalNode(
            capital_name=config.capital.capital_name,
            backend=MemoryStorageBackend(),
            entry=NetworkEntry(name=config.name, address=NetworkAddress(ip='0.0.0.0', port=8080)),
            peers=[]
        )

def launch_application(
    config: RunnerConfig
) -> None:
    try:
        # Launch the node.
        node: RawNode = get_application_node(config)

        LOGGER.info(f'Started node.')

        while True:
            time.sleep(0.5)

    finally:
        node.shutdown()

def main():
    setup_logging()
    

    if 'CONFIG_NAME' not in os.environ:
        raise RuntimeError(f'No CONFIG_NAME environment variable specified.')
    config: RunnerConfig = load_config(os.environ['CONFIG_NAME'])
    LOGGER.info(f'Found configuration {config}')

    


    launch_application(config)


if __name__ == "__main__":
    main()