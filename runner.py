from json import load
import os
import logging
import time
from typing import List

from colorama import Fore


from backend.common.components.storage.memory import MemoryStorageBackend
from backend.common.components.util import NetworkAddress, NetworkEntry
from backend.common.raw import RawNode
from backend.implementation.capital.server import CapitalNode
from backend.implementation.infrastructure.common import InfrastructureNode
from backend.implementation.regional.base import RegionalNode
from backend.runners.config import CapitalSpecificConfig, RunnerConfig
from backend.runners.registry import ServiceRegistry
def setup_logging():
    """
    Configure the application logging.
    """
    logging.basicConfig(
        level=logging.INFO,
        format=f" {Fore.YELLOW}(%(levelname)s) {Fore.LIGHTBLACK_EX}[%(name)s]{Fore.RESET} %(message)s",
        handlers=[
            logging.StreamHandler()
        ]
    )

LOGGER = logging.getLogger(__name__)

def load_config(name: str) -> RunnerConfig:
    """
    Loads the config given a specific name, allowing
    us to run that specific type of node.

    Args:
        name (str): The name we would like to load.

    Returns:
        RunnerConfig: The runner config which describes
        the node and how it should operate.
    """
    full_path: str = os.path.join('configs/fly', f'{name}.json')
    with open(full_path, 'r') as fi:
        return RunnerConfig.model_validate(load(fi))

def resolve_peers(
        peer_names: List[str],
        service: ServiceRegistry
) -> List[NetworkEntry]:
    return [ NetworkEntry(name=name, address=service.get_address(name)) for name in peer_names ]
    
def get_application_node(
    config: RunnerConfig,
    service: ServiceRegistry
) -> CapitalNode | RegionalNode | InfrastructureNode:
    """
    Builds an application node from the given
    runner config.

    Args:
        config (RunnerConfig): The runner config that
        describes the node and how it should be operated.
        service (ServiceRegistry): Provides the actual registry
        to access the services.

    Returns:
        CapitalNode | RegionalNode | InfrastructureNode: The actual node.
    """
    if service.service_is_local():
        # If we are local then we will use our generated
        # port number on the localhost IP.
        address = service.get_address(config.name)
    else:
        # If we are remote then we host on port 8080.
        address = NetworkAddress(ip='0.0.0.0', port=8080)

    logging.info(f'Assigned network details: {address}')
    # print(f'Address: {address}')
    if config.variant == 'capital':
        capital_spec: CapitalSpecificConfig = config.capital
        return CapitalNode(
            capital_name=capital_spec.capital_name,
            backend=MemoryStorageBackend(),
            entry=NetworkEntry(name=config.name, address=address),
            peers=resolve_peers(capital_spec.peers, service)
        )

def launch_application(
    config: RunnerConfig,
    service: ServiceRegistry
) -> None:
    """
    Launches & runs the application given the configuration.

    Args:
        config (RunnerConfig): The configuration we would
        like to use for the node.
        service (ServiceRegistry): Provides the actual addresses
        to the various services.
    """
    try:
        # Launch the node.
        node: RawNode = get_application_node(config, service)
        if service.service_is_local():
            node.enable_simulated_delays()

        LOGGER.info(f'Started node.')

        while True:
            time.sleep(0.5)

    finally:
        node.shutdown()

def main():
    # Configure the logger.
    setup_logging()

    is_local = "LOCAL" in os.environ and len(os.environ["LOCAL"]) > 0
    if is_local:
        logging.info("We are running the application locally.")
    
    
    # Validate that the CONFIG_NAME is specified and load the configuration.
    if 'CONFIG_NAME' not in os.environ:
        raise RuntimeError(f'No CONFIG_NAME environment variable specified.')
    config: RunnerConfig = load_config(os.environ['CONFIG_NAME'])
    LOGGER.info(f'Found configuration {config}')

    # Launch the application.
    launch_application(config, service=ServiceRegistry(is_local))


if __name__ == "__main__":
    main()