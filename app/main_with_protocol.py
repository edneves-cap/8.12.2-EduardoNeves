import os, json, time, threading
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

TRANSPORT = os.getenv("PIXKIT_TRANSPORT", "mqtt").lower()
DEVICE_ID = os.getenv("PIXKIT_DEVICE_ID", "pixkit-car-001")

# Session state init
if "telemetry_buffer" not in st.session_state:
    st.session_state.telemetry_buffer = []  # list of dicts
if "connected" not in st.session_state:
    st.session_state.connected = False
if "last_ack" not in st.session_state:
    st.session_state.last_ack = None
if "command_busy" not in st.session_state:
    st.session_state.command_busy = False

st.title = 'UI test'

'''# Transport selection
client = None
if TRANSPORT == "mqtt":
    from transport_mqtt import PixkitMqttClient
    client = PixkitMqttClient(
        device_id=DEVICE_ID,
        on_telemetry=lambda msg: st.session_state.telemetry_buffer.append(msg),
        on_ack=lambda ack: setattr(st.session_state, "last_ack", ack),
        on_connected=lambda: setattr(st.session_state, "connected", True),
        on_disconnected=lambda: setattr(st.session_state, "connected", False),
    )
elif TRANSPORT == "ws":
    from transport_ws import PixkitWsClient
    client = PixkitWsClient(
        device_id=DEVICE_ID,
        on_telemetry=lambda msg: st.session_state.telemetry_buffer.append(msg),
        on_ack=lambda ack: setattr(st.session_state, "last_ack", ack),
        on_connected=lambda: setattr(st.session_state, "connected", True),
        on_disconnected=lambda: setattr(st.session_state, "connected", False),
    )
else:
    st.stop()'''

# Background connect on first run
def ensure_connected():
    if not st.session_state.connected:
        threading.Thread(target=client.connect, daemon=True).start()

ensure_connected()

# --- UI Layout ---
st.set_page_config(page_title="Pixkit Remote Control", layout="wide")
st.title("Pixkit Car — Remote Control Interface")

col_status, col_device, col_ack = st.columns([1,1,1])
with col_status:
    st.metric("Connection", "Connected" if st.session_state.connected else "Disconnected")
with col_device:
    st.metric("Device ID", DEVICE_ID)
with col_ack:
    st.write("Last Ack:")
    st.code(json.dumps(st.session_state.last_ack or {}, indent=2))

st.divider()

# Controls panel
st.subheader("Controls")
c1, c2, c3, c4 = st.columns([1,1,1,1])

with c1:
    if st.button("Start", use_container_width=True, type="primary", disabled=st.session_state.command_busy):
        st.session_state.command_busy = True
        client.send_command("start", {})
        st.session_state.command_busy = False

    if st.button("Stop", use_container_width=True, disabled=st.session_state.command_busy):
        st.session_state.command_busy = True
        client.send_command("stop", {})
        st.session_state.command_busy = False

with c2:
    mode = st.selectbox("Drive Mode", ["manual", "cruise", "sport", "eco"])
    throttle = st.slider("Throttle", min_value=0.0, max_value=1.0, value=0.0, step=0.01)
    steering = st.slider("Steering", min_value=-1.0, max_value=1.0, value=0.0, step=0.01)
    apply = st.button("Apply Controls", use_container_width=True)
    if apply:
        # bounds safety check
        client.send_command("set_controls", {"mode": mode, "throttle": throttle, "steering": steering})

with c3:
    lights = st.selectbox("Lights", ["off", "low", "high", "hazard"])
    horn = st.checkbox("Horn", value=False)
    if st.button("Update Aux", use_container_width=True):
        client.send_command("set_aux", {"lights": lights, "horn": horn})

    st.markdown("**Emergency**")
    if st.button("EMERGENCY STOP", use_container_width=True):
        client.send_command("emergency_stop", {"reason": "user_trigger"})

with c4:
    st.markdown("**Firmware**")
    fw_ver = st.text_input("Target FW version", value="1.0.0")
    if st.button("Update Firmware", use_container_width=True):
        client.send_command("firmware_update", {"version": fw_ver})

st.divider()

# Telemetry
st.subheader("Live Telemetry")
buffer = st.session_state.telemetry_buffer[-500:]  # keep last 500
df = pd.DataFrame(buffer)

# When empty, show placeholder
if df.empty:
    st.info("Waiting for telemetry...")
else:
    # Expect telemetry schema: { deviceId, status, metrics{ speed, battery, temperature }, ts, seq, gps{lat,lon} }
    # Normalize metrics dict
    metrics = pd.json_normalize(df["metrics"])
    base = df[["ts", "status"]].reset_index(drop=True)
    merged = pd.concat([base, metrics], axis=1)

    cA, cB = st.columns([2,1])
    with cA:
        st.line_chart(merged.set_index("ts")[["speed", "battery"]], height=240)
        st.line_chart(merged.set_index("ts")[["temperature"]], height=180)
    with cB:
        st.write("Status samples")
        st.dataframe(df[["ts", "status", "seq"]].tail(10), use_container_width=True)

    st.expander("Raw telemetry (last 50)").dataframe(df.tail(50), use_container_width=True)

st.divider()
st.subheader("Audit / Logs")
st.caption("Prototype: showing last acks & commands only")
st.write("Last Ack")
st.code(json.dumps(st.session_state.last_ack or {}, indent=2))
