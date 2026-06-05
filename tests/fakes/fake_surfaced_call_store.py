from __future__ import annotations

from datetime import datetime, timedelta

from domain.surfaced_call import CallOutcome, Horizon, SurfacedCall


class FakeSurfacedCallStore:
    def __init__(self) -> None:
        self.saved: list[SurfacedCall] = []
        self.outcomes: list[CallOutcome] = []

    def save_call(self, call: SurfacedCall) -> None:
        self.saved.append(call)

    def get_call(self, call_id: str) -> SurfacedCall | None:
        return next((c for c in self.saved if c.call_id == call_id), None)

    def get_all_calls(self) -> list[SurfacedCall]:
        return list(self.saved)

    def get_due_calls(self, now: datetime) -> list[tuple[SurfacedCall, Horizon]]:
        resolved = {(o.call_id, o.horizon) for o in self.outcomes}
        return [
            (c, h)
            for c in self.saved
            for h in Horizon
            if (c.call_id, h) not in resolved
            and now >= c.surfaced_at + timedelta(days=h.value)
        ]

    def save_outcome(self, outcome: CallOutcome) -> None:
        self.outcomes.append(outcome)

    def get_outcomes(self) -> list[CallOutcome]:
        return list(self.outcomes)
