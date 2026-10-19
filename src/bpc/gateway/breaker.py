"""Circuit breaker (A5): closed -> open after `failure_threshold` consecutive
failures; open rejects instantly for `cooldown_s`; then half-open lets a single
probe through, which closes the circuit on success or re-opens it on failure."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

STATE_VALUE = {"closed": 0, "half_open": 1, "open": 2}


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    cooldown_s: float = 30.0
    state: str = "closed"
    failures: int = 0
    opened_at: float = 0.0
    probe_in_flight: bool = False
    transitions: list[tuple[float, str]] = field(default_factory=list)

    def _set(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self.transitions.append((time.time(), state))
            self.transitions = self.transitions[-50:]

    def allow(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.monotonic() - self.opened_at >= self.cooldown_s:
                self._set("half_open")
                self.probe_in_flight = True
                return True
            return False
        # half-open: one probe at a time
        if self.probe_in_flight:
            return False
        self.probe_in_flight = True
        return True

    def success(self) -> None:
        self.failures = 0
        self.probe_in_flight = False
        self._set("closed")

    def failure(self) -> None:
        self.probe_in_flight = False
        self.failures += 1
        if self.state == "half_open" or self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()
            self._set("open")

    def reset(self) -> None:
        self.failures = 0
        self.probe_in_flight = False
        self._set("closed")

    def snapshot(self) -> dict:
        return {
            "provider": self.name, "state": self.state, "consecutive_failures": self.failures,
            "cooldown_s": self.cooldown_s,
            "seconds_until_probe": max(0.0, self.cooldown_s - (time.monotonic() - self.opened_at))
            if self.state == "open" else 0.0,
            "transitions": [{"at": t, "state": s} for t, s in self.transitions[-10:]],
        }
