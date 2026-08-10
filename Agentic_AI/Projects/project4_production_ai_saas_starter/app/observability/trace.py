"""Per-request tracing.

Every agent run produces one Trace: an ordered list of steps, token counts,
cost, and wall-clock latency. Traces are appended to a JSONL file so a failing
eval case can be replayed and read step by step instead of guessed at.

Deliberately dependency-free. Langfuse or OTel would slot in behind the same
`Trace` surface; the point here is that the data exists, not which vendor holds it.
"""

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from app.config import TRACE_DIR, cost_usd


@dataclass
class Step:
    kind: str  # "model" | "tool" | "guardrail"
    name: str
    duration_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Trace:
    trace_id: str
    case_id: Optional[str] = None
    provider: str = "unknown"
    steps: list[Step] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    duration_ms: int = 0
    ok: bool = False
    error: Optional[str] = None

    @classmethod
    def start(cls, case_id: Optional[str] = None, provider: str = "unknown") -> "Trace":
        return cls(trace_id=uuid.uuid4().hex[:12], case_id=case_id, provider=provider)

    def add(self, step: Step) -> None:
        self.steps.append(step)

    def finish(self, ok: bool, error: Optional[str] = None) -> "Trace":
        self.duration_ms = int((time.time() - self.started_at) * 1000)
        self.ok = ok
        self.error = error
        return self

    @property
    def input_tokens(self) -> int:
        return sum(s.input_tokens for s in self.steps)

    @property
    def output_tokens(self) -> int:
        return sum(s.output_tokens for s in self.steps)

    @property
    def cost_usd(self) -> float:
        return cost_usd(self.input_tokens, self.output_tokens)

    @property
    def tools_called(self) -> list[str]:
        return [s.name for s in self.steps if s.kind == "tool"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "case_id": self.case_id,
            "provider": self.provider,
            "ok": self.ok,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "tools_called": self.tools_called,
            "steps": [asdict(s) for s in self.steps],
        }

    def write(self, filename: str = "traces.jsonl") -> str:
        os.makedirs(TRACE_DIR, exist_ok=True)
        path = os.path.join(TRACE_DIR, filename)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(self.to_dict()) + "\n")
        return path


class timed:
    """Context manager returning elapsed milliseconds.

        with timed() as t:
            ...
        t.ms
    """

    def __enter__(self) -> "timed":
        self._start = time.time()
        self.ms = 0
        return self

    def __exit__(self, *exc: object) -> None:
        self.ms = int((time.time() - self._start) * 1000)
