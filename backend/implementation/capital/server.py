from ...common.node.raw import RawNode
from ...common.node.layers.routing.routing_layer import node_handler
from ...common.node.common.plugins.leader_elec.bully_plugin import BullyPlugin
from ...common.node.common.plugins.heartbeat.capital_heartbeat_plugin import CapitalHeartbeatPlugin

from ...common.node.common.patching.mpatch import ManagedState
from ...common.node.common.plugins.leader_elec.bully_state_machine import BullyPeer

import threading
import datetime
import time
import hashlib
import json

from typing import Optional

from ...common.node.common.sync.signal import HoldSignal
from ...common.node.common.plugins.replication.replication_plugin import ReplicationPlugin

def _source_manager() -> ManagedState:
    state_infrastructure = {
        "power": "stable",
        "medical_capacity": 100,
        "transport": "operational",
        "water_capacity": 100,
        "fuel_storage": 100,
    }
    return ManagedState.from_dict(1, {
        "heartbeat": {},
        "state": {
            "Capital": {
                "state": state_infrastructure,
                "meta": {
                    "region_type": "CapitalNode",
                    "sites": []
                }
            }
        }
    })


from ...common.node.common.storage.memory import MemoryStorageBackend

class CapitalNode(RawNode):
    def __init__(
        self,
        network_name: str,
        address: tuple[str, int],
        peer_addresses: list[tuple[str, str, int]],
        seed_leader_name: str | None = None,
        bootstrap_leader: bool = False,
    ):
        self.peer_addresses = peer_addresses
        self.peer_names = [name for name, _, _ in peer_addresses if name != network_name]

        self.last_leader_heartbeat = time.time()
        self.leader_timeout_ms = 3000

        self.election_lock = threading.Lock()
        self.election_in_progress = False
        self.received_ok = False
        self.awaiting_coordinator = False
        self.coordinator_deadline = None

        self.lock = threading.Lock()
        self.proxy_lock = threading.Lock()

        self.replica_state = _source_manager()
        self.ready = bootstrap_leader
        self.ready_evt = threading.Event()
        if self.ready:
            self.ready_evt.set()

        self.sync_event = threading.Event()
        self.address = address

        self.current_leader = network_name if bootstrap_leader else seed_leader_name
        self.current_capital = network_name if bootstrap_leader else seed_leader_name
        self.is_leader = bootstrap_leader
        self.is_capital = bootstrap_leader

        super().__init__(network_name=network_name, address=address)

        self.replica_ready_signal = HoldSignal()
        self.fast_forward_signal = HoldSignal()

        self.bully_plugin = self.register_plugin(
            BullyPlugin(
                host=self,
                node=BullyPeer(
                    name=self.network_name,
                    unique_id=self._unique_id_from_name(self.network_name),
                    priority=self._priority_from_peer_count(),
                ),
                peers={
                    BullyPeer(
                        peer_name,
                        self._unique_id_from_name(peer_name),
                        self._priority_from_peer_count(),
                    ): (peer_name, peer_ip, peer_port)
                    for peer_name, peer_ip, peer_port in peer_addresses
                },
                verbose=False
            )
        )

        self.replication_plugin = self.register_plugin(ReplicationPlugin(
            host=self,
            name=self.get_network_name(),
            backend=MemoryStorageBackend(),
            replicas=self.peer_names,
            routes=[
                ('api.update_state', self.handle_test)
            ]
        ))

        # self.capital_heartbeat_plugin = self.register_plugin(
        #     CapitalHeartbeatPlugin(host=self)
        # )

        self.__internal_state = { 'state': {} }

        loaded: Optional[dict] = self.replication_plugin.load_state()
        if loaded is not None:
            print(f'[{self.network_name}] Restored state from snapshot.')
            self.__internal_state = loaded

        self.ready_to_handle()

    def handle_test(self, body: dict):
        print("UPDATE STATE REPLACED")

        name: str = body['name']
        data: str = body['state']

        self.__internal_state['state'][name] = data
        self.replication_plugin.commit(self.__internal_state)

        self._print_state_hash2()

        # import colorama
        # print(f'{colorama.Fore.GREEN}[US]{colorama.Fore.RESET} [{self.network_name}] body ~ {body} ')

    # def _connect_to(self, address: tuple[str, int]):
    #     if hasattr(self, "connect") and callable(getattr(self, "connect")):
    #         return self.connect(address)
    #     if hasattr(self, "_net_connect") and callable(getattr(self, "_net_connect")):
    #         return self._net_connect(address)
    #     raise AttributeError("RawNode does not expose connect or _net_connect")

    # def _disconnect_name(self, name: str):
    #     if hasattr(self, "disconnect") and callable(getattr(self, "disconnect")):
    #         print(f'PATH DN-1')
    #         return self.disconnect(name)
    #     if hasattr(self, "_net_disconnect") and callable(getattr(self, "_net_disconnect")):
    #         print(f'PATH DN-2')
    #         return self._net_disconnect(name)
    #     if hasattr(self, "connection_map"):
    #         print(f'PATH DN-3')
    #         try:
    #             return self.connection_map.deregister(name)
    #         except Exception:
    #             pass
    #     raise AttributeError("RawNode does not expose disconnect/_net_disconnect/connection_map.deregister")

    def _outbound_names(self) -> list[str]:
        if hasattr(self, "connection_map"):
            if hasattr(self.connection_map, "get_outbound_names"):
                return self.connection_map.get_outbound_names()
            if hasattr(self.connection_map, "get_connection_names"):
                return self.connection_map.get_connection_names()
        return []

    def _priority_from_peer_count(self) -> int:
        return len(self.peer_addresses)

    def _unique_id_from_name(self, name: str) -> str:
        return f"{name}-uid"

    def _node_id_from_name(self, name: str) -> int:
        try:
            return int(name.split("-")[-1])
        except Exception:
            return -1

    def _peer_addr_by_name(self, peer_name: str):
        for name, host, port in self.peer_addresses:
            if name == peer_name:
                return (host, port)
        return None
    
    def _print_state_hash2(self):
        serialized = json.dumps(
            obj=self.__internal_state,
            default=lambda x: str(x),
            sort_keys=True,
        )
        role = "leader" if self.is_leader else "follower"
        print(
            f"[{self.network_name} | {role}] version={self.replication_plugin.get_version_locked()}, "
            f"data={hashlib.sha256(serialized.encode()).hexdigest()}"
        )

    # def _print_state_hash(self):
    #     serialized = json.dumps(
    #         obj=self.replica_state.inspect_dict(),
    #         default=lambda x: str(x),
    #         sort_keys=True,
    #     )
    #     role = "leader" if self.is_leader else "follower"
    #     print(
    #         f"[{self.network_name} | {role}] version={self.replica_state.version}, "
    #         f"data={hashlib.sha256(serialized.encode()).hexdigest()}"
    #     )

    def multicast(self, target_glob: str, route: str, body: dict, include_self: bool = False):
        prefix = target_glob[:-1] if target_glob.endswith("*") else target_glob
        for name in self._outbound_names():
            if not include_self and name == self.network_name:
                continue
            if not name.startswith(prefix):
                continue
            try:
                self.send_message(name, route, body, timeout=1.0)
            except Exception:
                try:
                    if self.has_connection(name):
                        self._net_disconnect(name)
                        # self._disconnect_name(name)
                except Exception:
                    pass

    @node_handler(internal_ms=500)
    def maintain_peer_links(self):
        for peer_name, peer_ip, peer_port in self.peer_addresses:
            if peer_name == self.network_name:
                continue
            if self.has_connection(peer_name):
                continue
            try:
                self._net_connect((peer_ip, peer_port))
            except Exception:
                pass

    @node_handler(name="api.who_is_leader")
    def handle_who_is_leader(self, _body: dict, _source=None):
        return {
            "leader": self.current_leader,
            "is_leader": self.is_leader,
        }

    # @node_handler(name='fast.forward')
    # def handle_fast_forward(self, _message):
    #     return {
    #         "__version": self.replica_state.version,
    #         "__state": self.replica_state.inspect_dict()
    #     }

    # @node_handler(name='version')
    # def handle_version(self, _):
    #     return {
    #         "version": self.replica_state.version
    #     }

    def on_start_election(self):
        pass

    def on_become_leader(self):
        print("BECAME LEADER!!")
        self.fast_forward_signal.hold()
        try:
            self.current_leader = self.network_name
            self.current_capital = self.network_name
            self.is_leader = True
            self.is_capital = True

            # We are now the leader.
            self.replication_plugin.set_leader(self.get_network_name())

            # versions = {}
            # for peer in self.peer_names:
            #     if peer == self.network_name:
            #         continue

            #     if not self.has_connection(peer):
            #         for (a, b, c) in self.peer_addresses:
            #             if a == peer:
            #                 try:
            #                     self._connect_to((b, c))
            #                 except Exception:
            #                     pass

            #     if not self.has_connection(peer):
            #         continue

            #     try:
            #         vers = self.send_message(peer, 'version', {}, timeout=1.0)['version']
            #         versions[peer] = vers
            #     except Exception:
            #         try:
            #             if self.has_connection(peer):
            #                 self._disconnect_name(peer)
            #         except Exception:
            #             pass
            #         continue

            # versions = list(versions.items())
            # versions.sort(key=lambda x: x[1], reverse=True)

            # if len(versions) > 0:
            #     name, top_version = versions[0]
            #     if self.replica_state.version < top_version:
            #         self.__fast_forward_to_target(name)
        finally:
            self.fast_forward_signal.ready()
            self.replica_ready_signal.ready()


    def on_elect_leader(self, leader, peer, target):
        self.current_leader = target
        self.current_capital = target
        self.is_leader = (target == self.network_name)
        self.is_capital = self.is_leader

        # try:
        #     vers = self.send_message(target, 'version', {}, timeout=1.0)['version']
        # except Exception:
        #     print(f'[{self.network_name}] Could not reach leader {target} for version check.')
        #     return

        # if vers > self.replica_state.version:
        #     self.__fast_forward_to_target(target)
        self.replication_plugin.set_leader(target)

        self.replica_ready_signal.ready()

    # def __commit_local_replica(self, tx_data: dict):
    #     print("COMMITTING LOCAL REPLICAS")
    #     result = self.replica_state.end_transaction(tx_data, apply=True)
    #     self._print_state_hash()
        # return result

    # def __proxy_call(self, call, proxy_name: str, data, source=None):
    #     with self.proxy_lock:
    #         _, result = call(data, source)
    #         if result is not None:
    #             proxy_payload = dict(data)
    #             if source is not None:
    #                 proxy_payload["__origin_source"] = source
    #             if proxy_name == "api.proxy.region.heartbeat" and "__heartbeat_ts" not in proxy_payload:
    #                 hb = self.replica_state.inspect_dict().get("heartbeat", {}).get(source, {})
    #                 ts = hb.get("last_contact")
    #                 if ts is not None:
    #                     proxy_payload["__heartbeat_ts"] = ts
    #             self.multicast('rm-*', proxy_name, proxy_payload, include_self=False)
    #     return {"status": "success"}

    # def apply_region_heartbeat(self, data, source: str):
    #     print(f'REGION HEARTBEAT')
    #     # with self.lock:
    #     #     state = self.replica_state.start_transaction()
    #     #     if source not in state['heartbeat']:
    #     #         state['heartbeat'][source] = {}

    #     #     ts = data.get("__heartbeat_ts")
    #     #     if ts is None:
    #     #         ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    #     #     state['heartbeat'][source]['last_contact'] = ts
    #     #     return None, self.__commit_local_replica(state)

    # def proxy_region_heartbeat(self, data: dict, source: str):
    #     return self.__proxy_call(
    #         call=self.apply_region_heartbeat,
    #         proxy_name='api.proxy.region.heartbeat',
    #         data=data,
    #         source=source
    #     )



    @node_handler(name="api.national_infrastructure")
    def get_national_status(self, _m):
        self.replica_ready_signal.barrier()

        while not self.replica_state.is_consistent():
            self.sync_event.wait()

        return {
            "__version": self.replica_state.version,
            "__state": self.replica_state.inspect_dict(),
            "leader": self.current_leader,
            "capital": self.current_capital,
        }

    @node_handler(name="api.get_region_state")
    def get_region_state(self, body: dict, _sender: str):
        region_name = body.get("name")
        if not region_name:
            return {"status": "fail", "reason": "missing region name"}

        state = self.replica_state.inspect_dict()
        region_state = state.get("state", {}).get(region_name)

        if region_state is None:
            return {"status": "fail", "reason": f"no saved state for region {region_name}"}

        return {
            "status": "success",
            "region": region_name,
            "data": region_state,
            "leader": self.current_leader,
            "capital": self.current_capital,
            "version": self.replica_state.version,
        }

    # @node_handler(internal_ms=1000)
    # def debug_leader_state(self):
    #     print(f"[{self.network_name}] leader={self.current_leader}, is_leader={self.is_leader}")