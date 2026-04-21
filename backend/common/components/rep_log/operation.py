from dataclasses import dataclass
from typing import Dict

from pydantic import BaseModel


# @dataclass
class Operation(BaseModel):
    sequence_number: int
    operation: Dict

    def get_seq_num(self) -> int:
        return self.sequence_number
    
    def get_operation(self) -> Dict:
        return self.operation