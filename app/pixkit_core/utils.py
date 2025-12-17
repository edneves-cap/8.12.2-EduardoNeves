from datetime import datetime
import time, random

def now_iso() -> str:
    """UTC timestamp in ISO format with microseconds."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))

def gen_correlation_id() -> str:
    """Simple, sortable correlation ID."""
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"
