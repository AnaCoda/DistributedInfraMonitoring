import logging

from colorama import Fore

from backend.common.components.rep_log.log import ReplicationLog

from ..plugin import Plugin
from ...template import NodeTemplate
from ...storage.backend import StorageBackend

from typing import Dict, List, Optional, Tuple

from .rep_state_machine import (
    ReplicationStateMachineState,
    ReplicationMsg,
    ReplicationOp,
    ReplicationStateMachine,
    Operation
)
from threading import Lock, Event

from dataclasses import asdict

from typing import Callable, Any

from ....layers.routing.routing_layer import node_handler

from functools import wraps

LOGGER = logging.getLogger("plugin::replication")

class ReplicationPlugin(Plugin):

    def __init__(
            self,
            host: NodeTemplate,
            name: str,
            backend: StorageBackend,
            replicas: List[str],
            routes: List[Tuple[str, Callable[..., Any]]]
        ):
        super().__init__(host)

        self.replicas = replicas
        self.log = ReplicationLog(backend)

        self.__op_map: Dict[str, Callable[..., Any]] = {}
        self.__register_routes(routes)

        self.leader: Optional[str] = None
        self.leader_event = Event()

        self.__operation_lock = Lock()
        self.__sync_lock = Lock()
    
    def is_leader(self) -> bool:
        return self.get_leader() is not None and self.leader == self.get_network_name()

    def get_leader(self) -> Optional[str]:
        return self.leader
    
    def set_leader(self, name: Optional[str]):
        self.leader = name
        if name is None:
            self.leader_event.clear()
        else:
            self.leader_event.set()

    def on_operation(self):
        if hasattr(self.host, "on_operation"):
            self.host.on_operation()

    # def is_leader(self) -> bool:
        # return 

    #     self.__core_lock = Lock()
    #     self.__core = ReplicationStateMachine(name, backend)
    #     self.__leader_evt = Event()
    #     self.__replicas = replicas

    #     self.__op_map: dict[str, Callable[..., Any]] = {}

    #     self.__register_routes(routes)

    # def serve_state_request(self, sequences: list[int]) -> Dict[str, Any]:
    #     with self.__core_lock:
    #         ol = self.__core.replication_log.retrieve_at_idxs(sequences)
    #         ol = [ asdict(o) for o in ol ]

    #         state = self.__core.replication_log.log_state
    #         return {
    #             'state': state,
    #             'logs': ol
    #         }

    # def is_leader(self) -> bool:
    #     return self.__core.is_leader()
    
    # def leader_hold(self):
    #     return self.__core._set_state(ReplicationStateMachineState.LEADER_SYNC)

    def get_seq_num(self) -> int:
        return self.log.get_sequence_pos()
        # return self.__core.replication_log.get_sequence_pos()

    def __register_routes(self, op_routes):
        for key, fn in op_routes:
            def make_bound(route_key):
                @wraps(fn)
                def bound(*args, **kwargs):
                    return self.__handle_operation({
                        'key': route_key,
                        'args': list(args),
                        'kwargs': kwargs
                    })
                return bound
            self.__op_map[key] = fn
            self._register_route(key, make_bound(key))
    #     # def bound(*args, **kwargs):

    

    # def set_leader(self, name: Optional[str]):
    #     with self.__core_lock:
    #         if name is None:
    #             self.__leader_evt.clear()
    #             if self.__core.is_leader():
    #                 self.__core._set_state(ReplicationStateMachineState.INIT)
    #         else:
    #             self.__leader_evt.set()
    #         self.__core.set_leader(name)

    # def __wait_leader(self):
    #     while not self.__leader_evt.is_set():
    #         self.__leader_evt.wait()

    #     with self.__core_lock:
    #         # If we are the leader there is an edge case
    #         # whereby we are not yet initialized.
    #         if self.__core.is_leader():
    #             self.__poll_unlocked()
            
    
    # def __poll_unlocked(
    #     self
    # ):
    #     polled: list[ReplicationMsg] = self.__core.poll()
    #     if len(polled) == 0:
    #         return
    #     for poll in polled:
    #         # print(f'>> [{self.get_network_name()}] Sending {poll}')
    #         if poll.target is None:
    #             continue
    #         if not self.has_connection(poll.target):
    #             continue
    #         try:
    #             self.send_message_no_wait(
    #                 target=poll.target,
    #                 body=asdict(poll),
    #                 method='plugin.replication'
    #             )
    #         except Exception:
    #             try:
    #                 self.disconnect(poll.target)
    #             except Exception:
    #                 pass
    def on_new_version(self):
        if hasattr(self.host, "on_new_version"):
            self.host.on_new_version()

    @node_handler(name='sync.request')
    def sync_request(self, body: dict, source: str):
        ids = body['sync']
        LOGGER.info(f'Node={source} requested logs={ids}')
        pulled = self.log.retrieve_at_idxs(ids)

        return {
            "operations": [ op.model_dump(mode='json') for op in pulled ]
        }

    def __execute_operation(
        self,
        operation: Operation
    ):
        with self.__operation_lock:
            if operation.sequence_number > self.get_seq_num() + 1:
                with self.__sync_lock:
                    LOGGER.info(f"We require a fast forward to sequence={operation.get_seq_num()}")
                    operations = self.send_message(self.get_leader(), 'sync.request', { 'sync': list(range(self.get_seq_num() + 1, operation.sequence_number + 1)) })['operations']
                    for op in operations:
                        op = Operation.model_validate(op)
                        out = self.__apply_operation(op)
                    LOGGER.info(f'We have fast forwarded succesfully to sequence={operation.get_seq_num()}')
                    return out
                
        # Execute the operation without the need for fast forward.
        with self.__operation_lock:
            return self.__apply_operation(operation)

    def __apply_operation(
        self,
        operation: Operation
    ):
        """

        Note: You MUST be holding the lock when you call this method.

        Args:
            operation (Operation): _description_
        """
        
        # Now we execute the real operation by referencing
        # into the operation map.
        args = operation.operation['args']
        kwargs = operation.operation['kwargs']
        key = operation.operation['key']

    
        output = self.__op_map[key](*args, **kwargs)

        # self.on_operation()
        if operation.sequence_number == self.get_seq_num() + 1:
            self.log.add_log(operation)
            self.on_new_version()
        
        # Now we commit the operation.
        # print(f'[AO] commiting w/ {operation.sequence_number}')
        # o = self.__core.receive(ReplicationMsg.from_op(ReplicationOp.COMMIT, { 'sequence': operation.sequence_number }))    
        # print(f'[AO] [{self.get_network_name()}] {o}')
        # return { 'ping': 1 }
        return output
    
    def load_state(self):
        return self.log.backend.read('meta', 'snapshot')
        # with self.__core_lock:
            # return self.__core.backend.read('meta', 'snapshot')
    
    def commit(self, state: dict):
        # with self.__core_lock:
        self.log.backend.write('meta', 'snapshot', state)

    def __wait_leader(self):
        while not self.leader_event.is_set():
            self.leader_event.wait()

    @node_handler(name='operate')
    def handle_operate_msg(self, body: dict, source: str):
        self.__wait_leader()
        if source not in self.replicas:
            return {
                # This is a protected route, so we will decline requests
                # that are not authorized to interact at this route.
                'status': 'fail',
                'message': 'unauthorized request, only for internal use of replicas.'
            }
        return self.__handle_operation(body)
    
    

    @node_handler(name='plugin.replication')
    def plugin_replication(self, body: dict, source: str):
        if source not in self.replicas:
            return {
                # This is a protected route, so we will decline requests
                # that are not authorized to interact at this route.
                'status': 'fail',
                'message': 'unauthorized request, only for internal use of replicas.'
            }
        # operation = Operation.model_validate(body)
        return self.__execute_operation(Operation.model_validate(body))
        
        # print(f'Received: {operation}')


    def __handle_operation(
        self,
        body: dict
    ):
        self.__wait_leader()

        if not self.is_leader():
            # If we are not the leader, then we simply will forward
            # these packets to the leader.
            LOGGER.info("Forwarding an operation to the leader.")
            return self.send_message(self.get_leader(), 'operate', body)
        else:
            LOGGER.info("Leader received an operation.")
            operation = Operation(sequence_number=self.log.get_sequence_pos() + 1, operation=body)
            
            # The leader executes the operation locally.
            out = self.__apply_operation(operation)

            for replica in filter(lambda x : x != self.get_network_name(), self.replicas):
                try:
                    self.send_message_no_wait(replica, 'plugin.replication', operation.model_dump(mode='json'))
                except Exception as e:
                    LOGGER.error(f'{Fore.RED}[{self.get_network_name()}] Failed to send to {replica} with error={e}{Fore.RESET}')
                    pass
            return out
        # # External operations must wait for the leader.
        # self.__wait_leader()



        # # The following requires manual locking and unlocking
        # # of the core lock so we do not accidentally enter into
        # # a deadlocked scenario.
        # with self.__core_lock:
        #     is_leader = self.__core.is_leader()


        # self.__core.wait_for_state(ReplicationStateMachineState.EXECUTING)

        # if is_leader:
        #     # In this case we can begin by executing the operation.
        #     operation = ReplicationMsg.from_op(ReplicationOp.OPERATION, Operation(self.__core.replication_log.get_sequence_pos() + 1, body))
        #     # print(f'Producing a message: {operation}')
        #     # print(f'Sequernce; {self.__core.replication_log.get_sequence_pos()}')

        #     # We begin by executing the operation.
        #     with self.__core_lock:
        #         # We then apply the operation.
        #         self.__core.receive(operation)
        #         output = self.__apply_operation(Operation(**operation.body))
        #         self.__poll_unlocked()

        #     for replica in filter(lambda x : x != self.get_network_name(), self.__replicas):
        #         # Forward the message to all of the nodes that are not ourselves.
        #         try:
        #             self.send_message_no_wait(replica, 'plugin.replication', asdict(operation))
        #         except Exception as e:
        #             print(f'{Fore.RED}[{self.get_network_name()}] Failed to send to {replica} with error={e}{Fore.RESET}')
        #             pass
        #         print(f'[{self.get_network_name()}] Succesfully replicated option to replica={Fore.YELLOW}{replica}{Fore.RESET} with body={Fore.LIGHTBLACK_EX}{body}{Fore.RESET}')
        #             # print(f'excepted {type(e)}')
        #     return output
        # else:
        #     # In this case we actually need to forward the message to the leader, which will handle it
        #     # and then we just take the response.
        #     return self.send_message(self.__core.get_leader(), 'operate', body)
    
    
   


    # def get_version_locked(self):
    #     # if self.__core_lock.
    #     return self.__core.replication_log.get_sequence_pos()

    # @node_handler(name='plugin.replication')
    # def handle_replication_msg(self, body: dict, source: str):
    #     self.__wait_leader()
    #     if source not in self.__replicas:
    #         return {
    #             # This is a protected route, so we will decline requests
    #             # that are not authorized to interact at this route.
    #             'status': 'fail',
    #             'message': 'unauthorized request, only for internal use of replicas.'
    #         }
    #         # print("UNAUTHORIZED")

        
    #     body: ReplicationMsg = ReplicationMsg(**body)
    #     body.op = ReplicationOp[body.op.split('.')[1]]


    #     import random
    #     # if self.get_network_name() == 'hello2' and body.op == ReplicationOp.OPERATION:
    #     #     self.  += 1
    #     #     if self.count >= 3 and self.count <= 6:
    #     #         print('CRASHING')
    #     #         # pass
    #     #         raise RuntimeError('I failed')
    #     # print(f'[{self.get_network_name()}] BRUH: {self.__core.replication_log.get_sequence_pos()}')


    #     # print(f'body: {body}')
    #     # print(f'[{self.get_network_name()}] Received {body}')
    #     with self.__core_lock:
    #         if body.op == ReplicationOp.OPERATION:
    #             self.__core.wait_for_state(ReplicationStateMachineState.EXECUTING)
    #             o = self.__core.receive(body)
    #             # self.__poll_unlocked()
    #             # print(f'[BOO] [{self.get_network_name()}] {o}')
    #             if o:
    #                 self.__apply_operation(Operation(**body.body))
    #             self.__poll_unlocked()
    #         elif body.op == ReplicationOp.SYNC_RESPONSE or body.op == ReplicationOp.RESEND:
                
    #             logs: list[Operation] = [ Operation(**ser_op) for ser_op in body.body['logs'] ]
                

    #             # It is crucial that we sort the operations.
    #             logs.sort(key=lambda k : k.get_seq_num())

    #             for op in logs:
    #                 self.__core.receive(ReplicationMsg.from_op(ReplicationOp.OPERATION, op))
    #                 self.__apply_operation(op)
    #                 self.__poll_unlocked()
                
    #             # For durability's sake, the persistence must come here:
    #             self.__core.receive(body)

    #             # print(f'LOGS: {logs}')
    #             # for ser_op in logs:
    #             #     ser_op = Operation(**ser_op)

    #             #     self.__core.receive(ReplicationMsg.from_op(ReplicationOp.OPERATION))
    #             #     print(f'SEROP: {ser_op}')
    #         else:
    #             # print(f'[{self.get_network_name()}] Handling alt: {body}')
    #             self.__core.receive(body)
    #         self.__poll_unlocked()
    #         # print(f'[{self.get_network_name()}] State: {self.__core.get_state()}')

    # @node_handler(internal_ms=200)
    # def poll_internal_node(self):
    #     with self.__core_lock:
    #         # print(f'Polling: {self.get_network_name()}')
    #         self.__poll_unlocked()
