
from typing import Optional

from colorama import Fore

from backend.common.layers.routing.routing_layer import RoutingLayer, node_handler


class SimulationLayer(RoutingLayer):

    def __init__(self):
        super().__init__()
        self.down = None

    @node_handler(name='sim.down')
    def handle_sim_down(self, body: dict):
        duration = body['duration']
        if duration < 0 or duration > 5000:
            return {
                'status': 'fail',
                'message': 'Cannot take down a node for the specified duration.'
            }
        
        print(f'{Fore.MAGENTA}[{self.get_network_name()}] Requested downtime with duration={body["duration"]}{Fore.RESET}')
        self.down = duration

    @node_handler(name='sim.connlist')
    def handle_conn_list(self, body: dict):
        return {
            'names': self._net_connlist()
        }

    def is_sim_down(self) -> Optional[int]:
        return self.down