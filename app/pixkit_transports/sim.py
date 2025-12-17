
# pixkit_transports/sim.py
import time, random
from typing import Dict, Optional
from dataclasses import dataclass
from pixkit_core.car import Car
from pixkit_core.utils import now_iso
from pixkit_core.events import Ack

@dataclass
class MockPolicy:
    """Controls latency & failure simulation for actions."""
    min_latency_ms: int = 100
    max_latency_ms: int = 800
    failure_rate: float = 0.0  # 0..1 proportion of actions that fail

class SimTransport:
    """
    Local simulation transport using the OO Car class.
    - Queues actions with a scheduled completion time.
    - Applies state changes at completion (success), then emits ack.
    - Emits failure acks without applying changes (to test error UX).
    """

    def __init__(self,
                 device_id: str,
                 on_telemetry,
                 on_ack):
        self.device_id = device_id
        self.on_telemetry = on_telemetry
        self.on_ack = on_ack
        self.car = Car(device_id=device_id)
        self.policy = MockPolicy()
        self._pending = []  # list of dicts: {cmd, params, meta, complete_at, will_fail}

    def set_policy(self, policy: MockPolicy) -> None:
        self.policy = policy

    def connect(self) -> None:
        pass  # no-op

    def disconnect(self) -> None:
        pass  # no-op

    def send_command(self, command: str, params: Optional[Dict] = None, meta: Optional[Dict] = None) -> None:
        params = params or {}
        meta = meta or {}
        # Decide latency and failure
        latency_ms = random.randint(self.policy.min_latency_ms, self.policy.max_latency_ms)
        will_fail = random.random() < float(self.policy.failure_rate)
        self._pending.append({
            "cmd": command,
            "params": params,
            "meta": meta,
            "complete_at": time.time() + latency_ms / 1000.0,
            "will_fail": will_fail,
        })

    def _apply_command(self, command: str, params: Dict) -> None:
        """Apply state change (only on success)."""
        c = command.lower()
        if c == "start":
            self.car.start()
        elif c == "stop":
            self.car.stop()
        elif c == "emergency_stop":
            self.car.emergency_stop()
        elif c == "set_controls":
            self.car.set_controls(
                params.get("mode", self.car.mode),
                params.get("throttle", self.car.throttle),
                params.get("steering", self.car.steering),
            )
        elif c == "set_aux":
            self.car.set_aux(
                params.get("lights", self.car.lights),
                params.get("horn", self.car.horn),
            )
        elif c == "firmware_update":
            self.car.update_firmware(params.get("version", self.car.firmware))

    def _emit_ack(self, action: Dict, accepted: bool, message: str) -> None:
        meta = action["meta"]
        ack = Ack(
            correlation_id=meta.get("correlationId", ""),
            command=action["cmd"],
            accepted=accepted,
            message=message,
            ts_end=now_iso(),
            result={
                "running": self.car.running,
                "status": self.car.status,
                "mode": self.car.mode,
                "throttle": self.car.throttle,
                "steering": self.car.steering,
                "lights": self.car.lights,
                "firmware": self.car.firmware,
            },
        )
        self.on_ack(ack.__dict__)

    def tick(self, noise_level: float = 0.1) -> None:
        """Advance physics and complete any due actions."""
        # Physics → telemetry emission
        snapshot = self.car.step(noise_level=noise_level)
        self.on_telemetry(snapshot)

        # Complete due actions
        now = time.time()
        due = [a for a in self._pending if a["complete_at"] <= now]
        self._pending = [a for a in self._pending if a["complete_at"] > now]

        for a in due:
            if a["will_fail"]:
                self._emit_ack(a, accepted=False, message="Simulated failure")
            else:
                self._apply_command(a["cmd"], a["params"])
                self._emit_ack(a, accepted=True, message="OK")
