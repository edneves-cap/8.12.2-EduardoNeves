
# simulator_mqtt.py
import os, json, time, random
from paho.mqtt import client as mqtt
from dotenv import load_dotenv

load_dotenv()

device_id = os.getenv("PIXKIT_DEVICE_ID", "pixkit-car-001")
base = os.getenv("MQTT_TOPIC_BASE", "pixkit")
topic_cmd = f"{base}/{device_id}/command"
topic_tel = f"{base}/{device_id}/telemetry"
topic_status = f"{base}/{device_id}/status"
topic_ack_prefix = f"{base}/ack/"

url = os.getenv("MQTT_URL", "mqtt://localhost:1883")
proto, rest = url.split("://", 1)
host, port = (rest.split(":") + ["1883"])[:2]
port = int(port)

client = mqtt.Client()
if proto == "mqtts":
    client.tls_set()

running = False
mode = "manual"
throttle = 0.0
steering = 0.0
speed = 0.0
battery = 95.0
temperature = 35.0
seq = 0

def publish_status():
    client.publish(topic_status, json.dumps({
        "deviceId": device_id,
        "status": "running" if running else "stopped",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
        "seq": seq,
    }), qos=1)

def publish_telemetry():
    global speed, battery, temperature, seq
    # Simple dynamics model
    target_speed = throttle * (10.0 if mode == "sport" else 7.0 if mode == "cruise" else 5.0)
    speed += (target_speed - speed) * 0.2
    speed = max(0.0, speed)
    battery -= 0.01 + throttle * 0.02
    battery = max(0.0, battery)
    temperature = 30.0 + throttle * 15.0 + random.uniform(-1, 1)
    seq += 1

    client.publish(topic_tel, json.dumps({
        "deviceId": device_id,
        "status": "running" if running else "stopped",
        "metrics": {
            "speed": round(speed, 2),
            "battery": round(battery, 2),
            "temperature": round(temperature, 2),
        },
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
        "seq": seq,
    }), qos=1)

def handle_command(payload):
    global running, mode, throttle, steering
    cmd = json.loads(payload.decode("utf-8"))
    c = cmd.get("command")
    params = cmd.get("params", {})
    if c == "start":
        running = True
    elif c == "stop":
        running = False
        throttle = 0.0
        speed = 0.0
    elif c == "set_controls":
        mode = params.get("mode", mode)
        throttle = float(params.get("throttle", throttle))
        steering = float(params.get("steering", steering))
        throttle = max(0.0, min(1.0, throttle))
        steering = max(-1.0, min(1.0, steering))
    elif c == "set_aux":
        pass
    elif c == "emergency_stop":
        running = False
        throttle = 0.0
    elif c == "firmware_update":
        pass

    client.publish(f"{topic_ack_prefix}{cmd.get('correlationId','')}", json.dumps({
        "correlationId": cmd.get("correlationId"),
        "deviceId": device_id,
        "accepted": True,
        "result": {"running": running, "mode": mode, "throttle": throttle},
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
    }), qos=1)

def on_connect(c, u, f, rc):
    print("Connected", rc)
    c.subscribe(topic_cmd)

def on_message(c, u, msg):
    handle_command(msg.payload)

client.on_connect = on_connect
client.on_message = on_message
client.connect(host, port, keepalive=30)
client.loop_start()

try:
    while True:
        publish_status()
        if running:
            publish_telemetry()
        else:
            # Publish idle telemetry occasionally
            publish_telemetry()
        time.sleep(1.0)
except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()
