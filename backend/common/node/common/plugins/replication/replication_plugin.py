from ..plugin import Plugin
from ...template import NodeTemplate
from ...storage.backend import StorageBackend

from typing import Optional

from .rep_state_machine import (
    ReplicationStateMachineState,
    ReplicationMsg,
    ReplicationOp,
    ReplicationStateMachine,
    Operation
)
from threading import Lock, Event, Condition

from dataclasses import asdict, dataclass

from ....layers.routing.routing_layer import node_handler


class ReplicationPlugin(Plugin):

    def __init__(
            self,
            host: NodeTemplate,
            name: str,
            backend: StorageBackend,
            replicas: list[str]
        ):
        super().__init__(host)

        self.__core_lock = Lock()
        self.__core = ReplicationStateMachine(name, backend)
        self.__leader_evt = Event()
        self.__replicas = replicas
        self.__state_condition = Condition()

    def set_leader(self, name: Optional[str]):
        with self.__core_lock:
            if name is None:
                self.__leader_evt.clear()
            else:
                self.__leader_evt.set()
            self.__core.set_leader(name)

    def __wait_leader(self):
        while not self.__leader_evt.is_set():
            self.__leader_evt.wait()
        
    
    def __poll_unlocked(
        self
    ):
        polled: list[ReplicationMsg] = self.__core.poll()
        if len(polled) == 0:
            return
        for poll in polled:
            self.send_message_no_wait(
                target=poll.target,
                body=asdict(poll),
                method='plugin.replication'
            )


    def __apply_operation(
        self,
        operation: Operation
    ):
        """

        Note: You MUST be holding the lock when you call this method.

        Args:
            operation (Operation): _description_
        """
        print(f'[{self.get_network_name()}] Applying {operation}')
        
        # Now we commit the operation.
        self.__core.receive(ReplicationMsg.from_op(ReplicationOp.COMMIT, { 'sequence': operation.sequence_number }))    
        return { 'ping': 1 }

    @node_handler(name='operate')
    def handle_operate(self, body: dict):
        
        # External operations must wait for the leader.
        self.__wait_leader()

        # The following requires manual locking and unlocking
        # of the core lock so we do not accidentally enter into
        # a deadlocked scenario.
        with self.__core_lock:
            is_leader = self.__core.is_leader()

        self.__core.wait_for_state(ReplicationStateMachineState.EXECUTING)

        if is_leader:
            # In this case we can begin by executing the operation.
            operation = ReplicationMsg.from_op(ReplicationOp.OPERATION, Operation(self.__core.replication_log.get_sequence_pos() + 1, body))
            
            # We begin by executing the operation.
            with self.__core_lock:
                # We then apply the operation.
                output = self.__apply_operation(Operation(**operation.body))

            for replica in filter(lambda x : x != self.get_network_name(), self.__replicas):
                # Forward the message to all of the nodes that are not ourselves.
                self.send_message(replica, 'plugin.replication', asdict(operation))
            return output
        else:
            # In this case we actually need to forward the message to the leader, which will handle it
            # and then we just take the response.
            return self.send_message(self.__core.get_leader(), 'operate', body)

    @node_handler(name='plugin.replication')
    def handle_replication_msg(self, body: dict, _: str):
        body: ReplicationMsg = ReplicationMsg(**body)
        body.op = ReplicationOp[body.op.split('.')[1]]
        # print(f'body: {body}')
        print(f'[{self.get_network_name()}] Received {body}')
        with self.__core_lock:
            if body.op == ReplicationOp.OPERATION:
                # self.__core.receive(body)
                self.__apply_operation(Operation(**body.body))
            else:
                self.__core.receive(body)
            self.__poll_unlocked()
            # print(f'[{self.get_network_name()}] State: {self.__core.get_state()}')

    @node_handler(internal_ms=50)
    def poll_internal_node(self):
        with self.__core_lock:
            # print(f'Polling: {self.get_network_name()}')
            self.__poll_unlocked()
