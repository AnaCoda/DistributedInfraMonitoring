from ..state_machine import StateMachine, StateMachineMessage, BaseStateMachine
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
        return ReplicationMsg.from_op_targeted(None, op, body)
    
    @staticmethod
    def from_op_targeted(target: str, op: ReplicationOp, body: dict):
        if is_dataclass(body):
            body = asdict(body)
        return ReplicationMsg(op, None, target, body)


class ReplicationStateMachineState(Enum):
    INIT = 0
    STARTED = 1
    EXECUTING = 2
    IN_OPERATION = 3
    REQUESTING_CATCHUP = 4
    WAITING_CATCHUP = 5

class ReplicationSMResponseCode(Enum):
    FAILED = 0
    SUCCESS = 1


class ReplicationSMTarget(Enum):
    LEADER = 0

class ReplicationStateMachine(BaseStateMachine):
    
    def __init__(
            self,
            name: str,
            backend: StorageBackend
        ):
        super().__init__(name, ReplicationStateMachineState.INIT)
        self.backend = backend
        self.replication_log = ReplicationLog(self.backend)
        self.current_op: Optional[Operation] = None
        self.leader: Optional[str] = None

    def is_leader(self) -> bool:
        return self.leader is not None and self.leader == self.get_name()

    def set_leader(self, value: Optional[str]):
        self.leader = value

    def get_leader(self) -> Optional[str]:
        return self.leader
    
    def modify_outbound(self, msg: ReplicationMsg):
        super().modify_outbound(msg)
        if msg.op == ReplicationOp.SYNC_REQUEST or msg.op == ReplicationOp.REQUEST_MISSING:
            msg.target = self.get_leader()
        
    

    def _on_poll(self):
        if self.get_state() == ReplicationStateMachineState.INIT and self.get_leader() is not None:
            if self.is_leader():
                # If we are the leader we can start right up.
                self._set_state(ReplicationStateMachineState.EXECUTING)
            else:
                self._enqueue(ReplicationMsg.from_op(ReplicationOp.SYNC_REQUEST, { 'sequence': self.replication_log.get_sequence_pos() }))
                self._set_state(ReplicationStateMachineState.STARTED)
        elif self.get_state() == ReplicationStateMachineState.REQUESTING_CATCHUP:
            self._enqueue(ReplicationMsg.from_op(ReplicationOp.REQUEST_MISSING, { 'logs': self.__required_ops() }))
            self._set_state(ReplicationStateMachineState.WAITING_CATCHUP)

        
    def __required_ops(self) -> list[int]:
        return list(range(self.replication_log.get_sequence_pos() + 1, self.current_op.get_seq_num() + 1))

    def __handle_leader_async(self, packet: StateMachineMessage) -> bool:
        if packet.op == ReplicationOp.REQUEST_MISSING:
            missing = packet.body['logs']
            logs = self.replication_log.retrieve_at_idxs(missing)
            self._enqueue(ReplicationMsg.from_op_targeted(packet.source, ReplicationOp.RESEND, { 'logs': logs }))
            return True
        elif packet.op == ReplicationOp.SYNC_REQUEST:
            sequence = packet.body['sequence']
            logs = self.replication_log.retrieve_logs(sequence + 1, None)
            self._enqueue(ReplicationMsg.from_op_targeted(packet.source, ReplicationOp.SYNC_RESPONSE, { 'logs': logs } ))
            return True
        else:
            return False

    def receive(self, packet: StateMachineMessage) -> bool:
        #TODO: Send the actual Sync request.
        # if self.get_state() == ReplicationStateMachineState.INIT:
        #     pass
        if self.get_state() == ReplicationStateMachineState.STARTED:
            if packet.op == ReplicationOp.SYNC_RESPONSE:
                logs = packet.body['logs']
                for log in logs:
                    self.replication_log.add_log(Operation(**log))
                self._set_state(ReplicationStateMachineState.EXECUTING)
            else:
                # We ignore all other packets.
                return
        elif self.get_state() == ReplicationStateMachineState.EXECUTING:
            if packet.op == ReplicationOp.OPERATION:
                operation = Operation(**packet.body)
                flag = False
                if operation.sequence_number == self.replication_log.get_sequence_pos() + 1:
                    flag = True
                    self._set_state(ReplicationStateMachineState.IN_OPERATION)
                    self.current_op = operation
                elif operation.sequence_number + 1 > self.replication_log.get_sequence_pos():
                    self._set_state(ReplicationStateMachineState.REQUESTING_CATCHUP)
                    self.current_op = operation
                    flag = False
                return flag
            elif self.is_leader():
                return self.__handle_leader_async(packet)
            else:
                # We did not handle any operation.
                return False
        elif self.get_state() == ReplicationStateMachineState.REQUESTING_CATCHUP:
            return False
        elif self.get_state() == ReplicationStateMachineState.WAITING_CATCHUP:
            if packet.op == ReplicationOp.RESEND:
                ops: list[Operation]  = [ Operation(**op) for op in packet.body['logs']  ]
                seqs: list[int] = [ op.sequence_number for op in ops ]
                seqs.sort()
                if seqs == self.__required_ops():
                    ops.sort(key = lambda k : k.get_seq_num())
                    # self.replication_log.add_log()
                    for op in ops:
                        self.replication_log.add_log(op)
                    self._set_state(ReplicationStateMachineState.EXECUTING)
                    return True
                else:
                    return False
            else:
                # We are currently waiting a catchup, so we will not
                # handle any messages right now.
                return False
        elif self.get_state() == ReplicationStateMachineState.IN_OPERATION:
            # print(f'IN OP')
            if packet.op == ReplicationOp.COMMIT:
                operation_num = int(packet.body['sequence'])
                if self.current_op.sequence_number == operation_num:
                    self.replication_log.add_log(self.current_op)
                    self.current_op = None
                    self._set_state(ReplicationStateMachineState.EXECUTING)
                    return True
                else:
                    # The sequence number does not check out so we
                    # reject this message.
                    return False
            elif self.is_leader():
                return self.__handle_leader_async(packet)
            else:
                # We only support COMMIT messages in this state.
                return False
        else:
            print(f'BAD NAME {self.get_name()}')
            print(f'BAD STATE {self.get_state()}')
            print(f'BAD PACKET {packet}')
            print(f'BAD LEADER {self.get_leader()}')
            raise Exception(f'State {self.get_state()} not yet sypported.')
        # return super().receive(packet)
