
# pixkit_transports/base.py
from typing import Callable, Optional, Dict

class BaseTransport:
    """
    Transport interface. Implementations must call:
      - on_telemetry(snapshot_dict)
      - on_ack(ack_dict)
    """

    def __init__(self,
                 device_id: str,
                 on_telemetry: Callable[[Dict], None],
                 on_ack: Callable[[Dict], None]):
        self.device_id = device_id
        self.on_telemetry = on_telemetry
        self.on_ack = on_ack

    def connect(self) -> None:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def send_command(self, command: str, params: Optional[Dict] = None, meta: Optional[Dict] = None) -> None:
        raise NotImplementedError

    def tick(self, **kwargs) -> None:
        raise NotImplementedError
