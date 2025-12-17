
# services/controller.py
from typing import Dict, Optional
from pixkit_core.utils import gen_correlation_id, now_iso
from pixkit_core.events import Action

class PixkitController:
    """
    Orchestrates UI actions -> transport, tracks pending actions, and exposes a simple API.
    Ready for swapping transports (sim, mqtt, ws, rest).
    """

    def __init__(self, transport):
        self.transport = transport
        self.pending: Dict[str, Action] = {}

    def set_mock_policy(self, min_ms: int, max_ms: int, failure_rate: float) -> None:
        """Update simulation policy (latency & failure rate) if supported."""
        if hasattr(self.transport, "set_policy"):
            from pixkit_transports.sim import MockPolicy
            self.transport.set_policy(MockPolicy(min_ms, max_ms, failure_rate))

    def execute(self, command: str, params: Optional[Dict] = None, requested_by: str = "local") -> str:
        """Create an Action, push to transport, return correlation_id."""
        params = params or {}
        corr = gen_correlation_id()
        action = Action(
            correlation_id=corr,
            command=command,
            params=params,
            requested_by=requested_by,
            ts_start=now_iso(),
        )
        self.pending[corr] = action
        # send with metadata (corr id + requested_by + ts_start)
        self.transport.send_command(command, params, meta={"correlationId": corr, "requestedBy": requested_by, "ts_start": action.ts_start})
        return corr

    def get_action(self, correlation_id: str) -> Optional[Action]:
        return self.pending.get(correlation_id)

    def clear_action(self, correlation_id: str) -> None:
        self.pending.pop(correlation_id, None)
