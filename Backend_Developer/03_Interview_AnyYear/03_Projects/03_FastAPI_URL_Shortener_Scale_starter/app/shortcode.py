"""Snowflake-style distributed ID generation -> base62 short codes.

Spec section 5. A single centralized counter (Redis INCR) would be simpler
but becomes the bottleneck/SPOF at real scale — Snowflake lets every app
instance mint IDs independently, using its own worker_id + local clock, with
no coordination needed between instances.
"""

import time

_B62_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


class SnowflakeID:
    """64-bit ID: 1 reserved | 41 timestamp_ms | 10 worker_id | 12 sequence."""

    EPOCH = 1704067200000  # 2024-01-01, arbitrary but fixed reference point

    def __init__(self, worker_id: int):
        if not (0 <= worker_id <= 0x3FF):
            raise ValueError("worker_id must fit in 10 bits (0-1023)")
        self.worker_id = worker_id
        self.sequence = 0
        self.last_ts = 0

    def next_id(self) -> int:
        ts = int(time.time() * 1000)
        if ts == self.last_ts:
            self.sequence = (self.sequence + 1) & 0xFFF
            if self.sequence == 0:
                # sequence exhausted (4096 IDs) within the same millisecond —
                # spin until the clock advances rather than risk a collision
                while ts <= self.last_ts:
                    ts = int(time.time() * 1000)
        else:
            self.sequence = 0
        self.last_ts = ts
        return ((ts - self.EPOCH) << 22) | (self.worker_id << 12) | self.sequence


def to_base62(num: int) -> str:
    if num == 0:
        return _B62_CHARS[0]
    result = []
    while num > 0:
        result.append(_B62_CHARS[num % 62])
        num //= 62
    return "".join(reversed(result))


def from_base62(code: str) -> int:
    num = 0
    for ch in code:
        num = num * 62 + _B62_CHARS.index(ch)
    return num
