
# app.py
import os, json, time
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from pixkit_core.events import compute_latency_ms
from pixkit_transports.sim import SimTransport
from services.controller import PixkitController


load_dotenv()
TRANSPORT = os.getenv("PIXKIT_TRANSPORT", "sim").lower()
DEVICE_ID = os.getenv("PIXKIT_DEVICE_ID", "pixkit-car-local")

st.set_page_config(page_title="Pixkit Car UI and Simulation", layout="wide")
st.title("Pixkit Car UI and Simulation")
st.caption("UI runs against a local simulation layer so behavior is consistent for later Pixkit integration.")

# -------------------------------
# Session init & wiring
# -------------------------------
def init_state():
    if "telemetry_buffer" not in st.session_state:
        st.session_state.telemetry_buffer = []
    if "logs" not in st.session_state:
        st.session_state.logs = []      # ack-centric logs
    if "activity" not in st.session_state:
        st.session_state.activity = []  # UI-side activity entries (intent + corrId)
    if "last_ack" not in st.session_state:
        st.session_state.last_ack = None
    if "connected" not in st.session_state:
        st.session_state.connected = True
    if "refresh_ms" not in st.session_state:
        st.session_state.refresh_ms = 1000
    if "noise_level" not in st.session_state:
        st.session_state.noise_level = 0.1
    if "latency_range" not in st.session_state:
        st.session_state.latency_range = (150, 900)
    if "failure_rate" not in st.session_state:
        st.session_state.failure_rate = 0.05  # 5% failures to test UX

    # Wire transport + controller once
    if "controller" not in st.session_state:
        def on_telemetry(msg):
            st.session_state.telemetry_buffer.append(msg)
            st.session_state.telemetry_buffer = st.session_state.telemetry_buffer[-1000:]

        def on_ack(ack):
            # ack is dict: {correlation_id, command, accepted, message, ts_end, result{...}}
            st.session_state.last_ack = ack
            # Look up action for latency
            action = st.session_state.controller.get_action(ack["correlation_id"])
            latency_ms = None
            if action:
                latency_ms = compute_latency_ms(action, type("AckObj",(object,),ack)())
                st.session_state.controller.clear_action(ack["correlation_id"])

            # Build log entry
            log_entry = {
                "type": "ack",
                "correlation_id": ack.get("correlation_id"),
                "command": ack.get("command"),
                "accepted": ack.get("accepted"),
                "message": ack.get("message"),
                "latency_ms": latency_ms,
                "ts_end": ack.get("ts_end"),
                "result": ack.get("result", {}),
            }
            st.session_state.logs.append(log_entry)
            st.session_state.logs = st.session_state.logs[-300:]

            # Immediate UI feedback
            if ack.get("accepted"):
                st.toast(f"✅ {ack.get('command')} OK ({latency_ms} ms)", icon="✅")
            else:
                st.toast(f"❌ {ack.get('command')} failed ({latency_ms} ms): {ack.get('message')}", icon="❌")

        # Choose transport
        if TRANSPORT == "sim":
            transport = SimTransport(device_id=DEVICE_ID, on_telemetry=on_telemetry, on_ack=on_ack)
            st.session_state.connected = True
        else:
            transport = None
            st.session_state.connected = False

        # Controller
        st.session_state.controller = PixkitController(transport)

        # Apply initial mock policy
        min_ms, max_ms = st.session_state.latency_range
        st.session_state.controller.set_mock_policy(min_ms, max_ms, st.session_state.failure_rate)

init_state()

def add_activity(command: str, params: dict, corr: str):
    st.session_state.activity.append({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "command": command,
        "params": params,
        "correlation_id": corr,
    })
    st.session_state.activity = st.session_state.activity[-200:]

# -------------------------------
# Sidebar: Simulation controls
# -------------------------------
with st.sidebar:
    st.header("Simulation Settings")
    st.session_state.refresh_ms = st.slider("Refresh interval (ms)", 250, 3000, st.session_state.refresh_ms, 50)
    st.session_state.noise_level = st.slider("Telemetry noise", 0.0, 1.0, st.session_state.noise_level, 0.05)

    min_lat, max_lat = st.session_state.latency_range
    min_lat = st.number_input("Min latency (ms)", min_value=0, max_value=5000, value=int(min_lat), step=50)
    max_lat = st.number_input("Max latency (ms)", min_value=0, max_value=5000, value=int(max_lat), step=50)
    st.session_state.latency_range = (min_lat, max_lat)

    st.session_state.failure_rate = st.slider("Failure rate", 0.0, 0.5, st.session_state.failure_rate, 0.01)
    # Push policy to controller
    st.session_state.controller.set_mock_policy(min_lat, max_lat, st.session_state.failure_rate)

    st.divider()
    st.header("Export Telemetry")
    fname = st.text_input("CSV filename", "pixkit_telemetry_export.csv")
    if st.button("Export CSV", width='stretch'):
        df = pd.DataFrame(st.session_state.telemetry_buffer)
        if df.empty:
            st.warning("No telemetry yet.")
        else:
            df.to_csv(fname, index=False)
            st.success(f"Exported {fname} ({len(df)} rows).")

# -------------------------------
# Activity Summary (top)
# -------------------------------
def render_activity_summary():
    logs_df = pd.DataFrame(st.session_state.logs)
    total = len(logs_df)
    successes = int(logs_df["accepted"].sum()) if total else 0
    failures = total - successes
    avg_latency = int(logs_df["latency_ms"].dropna().mean()) if total and logs_df["latency_ms"].notna().any() else None

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Actions", total)
    with c2:
        st.metric("Successes", successes)
    with c3:
        st.metric("Failures", failures)
    with c4:
        st.metric("Avg Latency (ms)", avg_latency if avg_latency is not None else "—")

render_activity_summary()
st.divider()

# -------------------------------
# Status & Last Ack
# -------------------------------
c_status, c_dev, c_ack = st.columns(3)
with c_status:
    st.metric("Connection", "Connected" if st.session_state.connected else "Disconnected")
with c_dev:
    st.metric("Device ID", DEVICE_ID)
with c_ack:
    st.write("Last Ack")
    st.code(json.dumps(st.session_state.last_ack or {}, indent=2))

st.divider()

# -------------------------------
# Controls → mock actions via controller
# -------------------------------
st.subheader("Controls")
c1, c2, c3, c4 = st.columns([1,1,1,1])

with c1:
    if st.button("Start", width='stretch', type="primary"):
        corr = st.session_state.controller.execute("start", {}, requested_by="ui")
        add_activity("start", {}, corr)

    if st.button("Stop", width='stretch'):
        corr = st.session_state.controller.execute("stop", {}, requested_by="ui")
        add_activity("stop", {}, corr)

with c2:
    # use last telemetry to prefill
    last = st.session_state.telemetry_buffer[-1] if st.session_state.telemetry_buffer else {}
    mode = st.selectbox("Drive Mode", ["manual","cruise","sport","eco"], index=["manual","cruise","sport","eco"].index(last.get("mode","manual")))
    throttle = st.slider("Throttle", 0.0, 1.0, float(last.get("throttle", 0.0)), 0.01)
    steering = st.slider("Steering", -1.0, 1.0, float(last.get("steering", 0.0)), 0.01)

    if st.button("Apply Controls", width='stretch'):
        params = {"mode": mode, "throttle": throttle, "steering": steering}
        corr = st.session_state.controller.execute("set_controls", params, requested_by="ui")
        add_activity("set_controls", params, corr)

with c3:
    lights = st.selectbox("Lights", ["off","low","high","hazard"], index=["off","low","high","hazard"].index(last.get("lights","off")))
    horn = st.checkbox("Horn", value=bool(last.get("horn", False)))
    if st.button("Update Aux", width='stretch'):
        params = {"lights": lights, "horn": horn}
        corr = st.session_state.controller.execute("set_aux", params, requested_by="ui")
        add_activity("set_aux", params, corr)

    st.markdown("**Emergency**")
    if st.button("EMERGENCY STOP", width='stretch'):
        corr = st.session_state.controller.execute("emergency_stop", {"reason": "user_trigger"}, requested_by="ui")
        add_activity("emergency_stop", {"reason": "user_trigger"}, corr)

with c4:
    fw_ver = last.get("firmware", "1.0.0")
    target_fw = st.text_input("Target FW version", value=str(fw_ver))
    if st.button("Update Firmware", width='stretch'):
        params = {"version": target_fw}
        corr = st.session_state.controller.execute("firmware_update", params, requested_by="ui")
        add_activity("firmware_update", params, corr)

st.divider()

# -------------------------------
# Telemetry tick & auto-refresh
# -------------------------------
if st.session_state.controller.transport:
    st.session_state.controller.transport.tick(noise_level=st.session_state.noise_level)

#st.autorefresh(interval=st.session_state.refresh_ms, key="auto_refresh")

# -------------------------------
# Telemetry display
# -------------------------------
st.subheader("Live Telemetry")
buf = st.session_state.telemetry_buffer[-500:]
df = pd.DataFrame(buf)

if df.empty:
    st.info("Waiting for telemetry...")
else:
    metrics_df = pd.json_normalize(df["metrics"])
    gps_df = pd.json_normalize(df["gps"])
    base_df = df[["ts","status","seq","mode","throttle","steering","lights","horn","firmware"]].reset_index(drop=True)
    merged = pd.concat([base_df, metrics_df, gps_df], axis=1)

    cA, cB = st.columns([3,2])
    with cA:
        st.line_chart(merged.set_index("ts")[["speed", "battery"]], height=240)
        st.line_chart(merged.set_index("ts")[["temperature"]], height=180)
    with cB:
        st.metric("Speed (km/h)", f"{merged['speed'].iloc[-1]:.2f}")
        st.metric("Battery (%)", f"{merged['battery'].iloc[-1]:.2f}")
        st.metric("Temperature (°C)", f"{merged['temperature'].iloc[-1]:.2f}")

        st.write("Status samples")
        st.dataframe(merged[["ts","status","seq","mode","throttle","steering"]].tail(10), width='stretch', height=240)

    st.divider()
    st.subheader("GPS (simulated)")
    st.dataframe(merged[["ts","lat","lon","speed","steering"]].tail(10), width='stretch')

    st.expander("Raw telemetry (last 50)").dataframe(pd.DataFrame(buf).tail(50), width='stretch')

# -------------------------------
# Activity & Logs panes
# -------------------------------
st.divider()
st.subheader("Activity (UI Intents)")
if len(st.session_state.activity) == 0:
    st.info("No activity yet.")
else:
    st.dataframe(pd.DataFrame(st.session_state.activity).tail(25), width='stretch', height=220)

st.subheader("Ack / Logs")
if len(st.session_state.logs) == 0:
    st.info("No acks yet.")
else:
    st.dataframe(pd.DataFrame(st.session_state.logs).tail(25), width='stretch', height=280)

# -------------------------------
# Quick actions
# -------------------------------
st.divider()
b1, b2, b3 = st.columns([1,1,2])
with b1:
    if st.button("Reset Telemetry", width='stretch'):
        st.session_state.telemetry_buffer = []
        st.toast("Telemetry buffer reset.", icon="✅")
with b2:
    if st.button("Recharge Battery", width='stretch'):
        # sim-only convenience
        if hasattr(st.session_state.controller.transport, "car"):
            st.session_state.controller.transport.car.battery_pct = 100.0
            st.toast("Battery recharged to 100%", icon="🔋")
with b3:
    st.caption("Swap to real transports later by implementing the same interface and updating `.env`.")
 