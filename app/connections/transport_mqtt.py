
# transport_mqtt.py
import os, json, time
from typing import Callable
from paho.mqtt import client as mqtt

class PixkitMqttClient:
    def __init__(self, device_id, on_telemetry: Callable, on_ack: Callable,
                 on_connected: Callable, on_disconnected: Callable):
        self.device_id = device_id
        self.on_telemetry = on_telemetry
        self.on_ack = on_ack
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected

        url = os.getenv("MQTT_URL", "mqtt://localhost:1883")
        # Parse URL simple
        proto, rest = url.split("://", 1)
        host_port = rest
        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host, port = host_port, 1883

        self.client = mqtt.Client()
        user = os.getenv("MQTT_USER", "")
        pw = os.getenv("MQTT_PASS", "")
        if user:
            self.client.username_pw_set(user, pw)

        # TLS optional: if proto == 'mqtts', enable tls
        if proto == "mqtts":
            self.client.tls_set()

        base = os.getenv("MQTT_TOPIC_BASE", "pixkit")
        self.topic_cmd = f"{base}/{device_id}/command"
        self.topic_tel = f"{base}/{device_id}/telemetry"
        self.topic_status = f"{base}/{device_id}/status"
        self.topic_ack_prefix = f"{base}/ack/"

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = lambda *_: self.on_disconnected()

        self.host, self.port = host, port

    def connect(self):
        self.client.connect(self.host, self.port, keepalive=30)
        self.client.loop_forever()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.on_connected()
            client.subscribe(self.topic_tel)
            client.subscribe(self.topic_status)
            client.subscribe(f"{self.topic_ack_prefix}+")
        else:
            self.on_disconnected()

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return
        topic = msg.topic
        if topic == self.topic_tel:
            data["type"] = "telemetry"
            self.on_telemetry(data)
        elif topic == self.topic_status:
            data["type"] = "status"
            self.on_telemetry(data)
        elif topic.startswith(self.topic_ack_prefix):
            data["type"] = "ack"
            self.on_ack(data)

    def send_command(self, command: str, params: dict):
        # Attach metadata
        payload = {
            "deviceId": self.device_id,
            "command": command,
            "params": params or {},
            "correlationId": str(int(time.time()*1000)),
            "requestedBy": os.getenv("USER", "streamlit"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self.client.publish(self.topic_cmd, json.dumps(payload), qos=1, retain=False)
