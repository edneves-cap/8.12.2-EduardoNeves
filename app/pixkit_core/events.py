from dataclasses import dataclass
from typing import Dict

from datetime import datetime

@dataclass
class Action:
    correlation_id: str
    command: str
    params: Dict
    requested_by: str
    ts_start: str

@dataclass
class Ack:
    ## acknowledgment (networks)
    correlation_id: str
    command: str
    accepted: bool
    message: str
    ts_end: str
    result: Dict

def compute_latency_ms(action: Action, ack: Ack) -> int:
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
    t0 = datetime.strptime(action.ts_start, fmt)
    t1 = datetime.strptime(ack.ts_end, fmt)
    return int((t1 - t0).total_seconds()*1000)
