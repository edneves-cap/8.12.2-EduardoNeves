
# transport_ws.py
import os, json, time
from websocket import create_connection

class PixkitWsClient:
    def __init__(self, device_id, on_telemetry, on_ack, on_connected, on_disconnected):
        self.device_id = device_id
        self.on_telemetry = on_telemetry
        self.on_ack = on_ack
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        self.ws_url = os.getenv("WS_URL", "wss://localhost:3000/ws")

    def connect(self):
        try:
            ws = create_connection(self.ws_url)
            self.on_connected()
            while True:
                msg = ws.recv()
                data = json.loads(msg)
                # Expect { type: 'telemetry'|'status'|'ack', deviceId: ... }
                if data.get("deviceId") != self.device_id:
                    continue
                t = data.get("type")
                if t in ("telemetry", "status"):
                    self.on_telemetry(data)
                elif t == "ack":
                    self.on_ack(data)
        except Exception:
            self.on_disconnected()

    def send_command(self, command, params):
        # For WS, we assume server expects a JSON envelope
        # Adjust to your backend contract.
        payload = {
            "deviceId": self.device_id,
            "type": "command",
            "command": command,
            "params": params or {},
            "correlationId": str(int(time.time()*1000)),
            "requestedBy": os.getenv("USER", "streamlit"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        # In a simple WS only-subscription scenario, you might POST via REST instead.
        # Here we demo a direct send if WS supports it:
        # NOTE: Streamlit runs in multiple threads; sending from here would require persistent ws.
        # For now, prefer MQTT for commands.
        pass
