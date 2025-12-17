
# pixkit_core/car.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple
import math, random
from .utils import clamp, now_iso

@dataclass
class Car:
    """Encapsulates Pixkit car state, controls, physics, and telemetry serialization."""
    device_id: str = "pixkit-car-local"
    firmware: str = "1.0.0"

    # Dynamic state
    running: bool = False
    status: str = "stopped"
    mode: str = "manual"               # manual | cruise | sport | eco
    throttle: float = 0.0              # 0..1
    steering: float = 0.0              # -1..1
    lights: str = "off"                # off | low | high | hazard
    horn: bool = False

    # Telemetry state
    speed_kmh: float = 0.0
    battery_pct: float = 100.0
    temperature_c: float = 28.0
    gps: Dict[str, float] = field(default_factory=lambda: {"lat": 41.133, "lon": -8.617})  
    seq: int = 0
    last_update: str = field(default_factory=now_iso)

    # Internal dynamics
    _heading_rad: float = field(default_factory=lambda: random.uniform(0, 2 * math.pi))

    # Controls
    def start(self) -> None:
        self.running = True
        self._sync_status()

    def stop(self) -> None:
        self.running = False
        self.throttle = 0.0
        self.speed_kmh = 0.0
        self._sync_status()

    def emergency_stop(self) -> None:
        self.running = False
        self.throttle = 0.0
        self.speed_kmh = 0.0
        self._sync_status()

    def set_controls(self, mode: str, throttle: float, steering: float) -> None:
        self.mode = mode
        self.throttle = clamp(float(throttle), 0.0, 1.0)
        self.steering = clamp(float(steering), -1.0, 1.0)

    def set_aux(self, lights: str, horn: bool) -> None:
        self.lights = lights
        self.horn = bool(horn)

    def update_firmware(self, version: str) -> None:
        self.firmware = str(version).strip()

    # Physics
    def _mode_max_speed(self) -> float:
        return {"manual": 8.0, "cruise": 10.0, "sport": 14.0, "eco": 7.0}.get(self.mode, 8.0)

    def _simulate_gps(self, speed_kmh: float, steering: float) -> Tuple[float, float]:
        speed_ms = speed_kmh / 3.6
        self._heading_rad += clamp(steering, -1, 1) * 0.08
        dx = speed_ms * math.cos(self._heading_rad) * 0.2  # ~1s step
        dy = speed_ms * math.sin(self._heading_rad) * 0.2
        dlat = dy / 111_000.0
        dlon = dx / (111_000.0 * math.cos(math.radians(self.gps["lat"])))
        return round(self.gps["lat"] + dlat, 6), round(self.gps["lon"] + dlon, 6)

    def step(self, noise_level: float = 0.1) -> Dict:
        target_speed = self.throttle * self._mode_max_speed()
        self.speed_kmh += (target_speed - self.speed_kmh) * 0.25
        self.speed_kmh = max(0.0, self.speed_kmh)

        base_drain = 0.005
        drain_noise = random.uniform(-0.002, 0.002) * noise_level
        self.battery_pct = clamp(self.battery_pct - (base_drain + self.throttle * 0.02 + drain_noise), 0.0, 100.0)

        temp_delta = (self.throttle * 0.8) - (0.05 if not self.running else 0.0)
        temp_noise = random.uniform(-0.05, 0.05) * noise_level
        self.temperature_c = clamp(self.temperature_c + temp_delta + temp_noise, 10.0, 90.0)

        nlat, nlon = self._simulate_gps(self.speed_kmh, self.steering)
        self.gps["lat"], self.gps["lon"] = nlat, nlon

        self._sync_status()
        self.seq += 1
        self.last_update = now_iso()
        return self.to_telemetry()

    def _sync_status(self) -> None:
        self.status = "running" if self.running else "stopped"

    # Serialization
    def to_telemetry(self) -> Dict:
        return {
            "deviceId": self.device_id,
            "status": self.status,
            "metrics": {
                "speed": round(self.speed_kmh, 3),
                "battery": round(self.battery_pct, 3),
                "temperature": round(self.temperature_c, 3),
            },
            "gps": {"lat": self.gps["lat"], "lon": self.gps["lon"]},
            "mode": self.mode,
            "throttle": round(self.throttle, 3),
            "steering": round(self.steering, 3),
            "seq": self.seq,
            "ts": self.last_update,
            "lights": self.lights,
            "horn": self.horn,
            "firmware": self.firmware,
        }
