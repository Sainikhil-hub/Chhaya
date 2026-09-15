"""Feature extraction from packet metadata.

REQ-4/5/6: extract (avg_packet_size, inter_packet_interval_ms,
packets_per_minute, burstiness) from packet metadata only - no payload
content is ever read.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, asdict
from typing import Iterable, Sequence

FEATURE_NAMES = (
    "avg_packet_size",
    "inter_packet_interval_ms",
    "packets_per_minute",
    "burstiness",
)


@dataclass
class FeatureVector:
    avg_packet_size: float
    inter_packet_interval_ms: float
    packets_per_minute: float
    burstiness: float

    def as_list(self) -> list[float]:
        return [getattr(self, f) for f in FEATURE_NAMES]

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def extract_features(packets: Sequence[tuple[float, int]],
                     window_seconds: float) -> FeatureVector | None:
    """Compute the feature vector for a single device's window.

    Parameters
    ----------
    packets : sequence of (timestamp, size_bytes)
        Packets observed from one source IP within the current window.
    window_seconds : float
        Length of the window in seconds (used for packets_per_minute).

    Returns
    -------
    FeatureVector or None
        None if there are not enough packets to produce a meaningful vector
        (less than 2 packets => no defined inter-packet interval).
    """
    if len(packets) < 2:
        return None

    sizes = [p[1] for p in packets]
    timestamps = sorted(p[0] for p in packets)

    intervals_ms = [
        (timestamps[i] - timestamps[i - 1]) * 1000.0
        for i in range(1, len(timestamps))
    ]
    intervals_ms = [max(iv, 0.001) for iv in intervals_ms]  # avoid divide-by-zero

    avg_size = sum(sizes) / len(sizes)
    avg_interval = sum(intervals_ms) / len(intervals_ms)

    # Burstiness = coefficient of variation of inter-packet intervals.
    # High -> irregular / spiky traffic. Low -> steady / periodic.
    if len(intervals_ms) >= 2 and avg_interval > 0:
        stdev = statistics.pstdev(intervals_ms)
        burstiness = stdev / avg_interval
    else:
        burstiness = 0.0

    packets_per_minute = (len(packets) / window_seconds) * 60.0 if window_seconds > 0 else 0.0

    return FeatureVector(
        avg_packet_size=round(avg_size, 2),
        inter_packet_interval_ms=round(avg_interval, 2),
        packets_per_minute=round(packets_per_minute, 2),
        burstiness=round(burstiness, 3),
    )


def safe_extract(packets: Sequence[tuple[float, int]],
                 window_seconds: float) -> FeatureVector:
    """Like extract_features but always returns a vector (zero-filled when
    not enough data). Used for the first window so the dashboard never
    receives a null feature set."""
    fv = extract_features(packets, window_seconds)
    if fv is not None:
        return fv
    return FeatureVector(0.0, 0.0, 0.0, 0.0)


def feature_distance(a: FeatureVector, b: FeatureVector) -> float:
    """Euclidean distance between two feature vectors in their raw space."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a.as_list(), b.as_list())))


def zscore(value: float, mean: float, std: float) -> float:
    if std <= 1e-9:
        return 0.0
    return (value - mean) / std
