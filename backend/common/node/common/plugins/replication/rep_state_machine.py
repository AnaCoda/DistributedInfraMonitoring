from ..state_machine import StateMachine, StateMachineMessage
from ...rep_log.log import ReplicationLog, ReplicationOutOfOrder, Operation
from dataclasses import dataclass, is_dataclass, asdict
from enum import Enum
from ...storage.backend import StorageBackend
from typing import Optional

class ReplicationOp(Enum):
    OPERATION = 0
    REQUEST_MISSING = 1
    RESEND = 2
    SYNC_REQUEST = 3
    SYNC_RESPONSE = 4
    COMMIT = 5

@dataclass
class ReplicationMsg(StateMachineMessage):
    pass

    @staticmethod
    def from_op(op: ReplicationOp, body: dict):
        if is_dataclass(body):
            body = asdict(body)
        return ReplicationMsg(op, body)


class ReplicationStateMachineState(Enum):
    STARTED = 0
    EXECUTING = 1
    IN_OPERATION = 2

class ReplicationStateMachine(StateMachine):
    
    def __init__(
            self,
            backend: StorageBackend
        ):
        super().__init__()
        self.backend = backend
        self.replication_log = ReplicationLog(self.backend)
        self._set_state(ReplicationStateMachineState.STARTED)
        # self.state = ReplicationStateMachineState.STARTED
        self.current_op: Optional[Operation] = None

    def get_state(self) -> ReplicationStateMachineState:
        return self.state

    def _set_state(self, state):
        self.state = state
        # return super()._set_state(state)
        # return super().get_state()

    def poll(self):
        if self.state == ReplicationStateMachineState.STARTED:
            # We need to fast forward.
            return [ ReplicationMsg(ReplicationOp.SYNC_REQUEST, { 'sequence': self.replication_log.get_sequence_pos() }) ]
        else:
            raise Exception(f'State {self.state} not yet supported.')
    

    def receive(self, packet) -> Optional[bool]:
        #TODO: Send the actual Sync request.
        if self.state == ReplicationStateMachineState.STARTED:
            if packet.op == ReplicationOp.SYNC_RESPONSE:
                logs = packet.body['logs']
                for log in logs:
                    self.replication_log.add_log(Operation(**log))
                self.state = ReplicationStateMachineState.EXECUTING
            else:
                # We ignore all other packets.
                return
        elif self.state == ReplicationStateMachineState.EXECUTING:
            if packet.op == ReplicationOp.OPERATION:
                operation = Operation(**packet.body)
                flag = False
                if operation.sequence_number == self.replication_log.get_sequence_pos() + 1:
                    flag = True
                    self.state = ReplicationStateMachineState.IN_OPERATION
                    self.current_op = operation
                return flag
            else:
                # We did not handle any operation.
                return False
        elif self.state == ReplicationStateMachineState.IN_OPERATION:
            if packet.op == ReplicationOp.COMMIT:
                operation_num = int(packet.body['sequence'])
                if self.current_op.sequence_number == operation_num:
                    self.replication_log.add_log(self.current_op)
                    self.current_op = None
                    self.state = ReplicationStateMachineState.EXECUTING
                    return True
                else:
                    # The sequence number does not check out so we
                    # reject this message.
                    return False
            else:
                # We only support COMMIT messages in this state.
                return False
        else:
            raise Exception(f'State {self.state} not yet sypported.')
        # return super().receive(packet)