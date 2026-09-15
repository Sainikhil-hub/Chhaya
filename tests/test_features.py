"""Tests for the feature extraction module (REQ-5)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.features import extract_features, safe_extract, feature_distance, zscore  # noqa: E402


def make_steady_packets(n: int = 10, interval_ms: float = 100.0,
                        size: int = 100, start: float = 1000.0):
    return [(start + i * interval_ms / 1000.0, size) for i in range(n)]


def make_bursty_packets(n: int = 10, sizes=None):
    sizes = sizes or [50, 80, 200, 60, 1500, 70, 90, 1500, 40, 100]
    ts = 1000.0
    out = []
    for i, s in enumerate(sizes):
        out.append((ts, s))
        # alternating short / long intervals -> bursty
        ts += 0.02 if i % 2 == 0 else 0.5
    return out


def test_extract_features_returns_none_when_too_few_packets():
    assert extract_features([(1000.0, 100)], 5.0) is None
    assert extract_features([], 5.0) is None


def test_safe_extract_returns_zero_vector_when_no_data():
    fv = safe_extract([], 5.0)
    assert fv.avg_packet_size == 0.0
    assert fv.burstiness == 0.0


def test_steady_packets_have_low_burstiness():
    pkts = make_steady_packets(n=10, interval_ms=100.0, size=100)
    fv = extract_features(pkts, 5.0)
    assert fv is not None
    assert fv.avg_packet_size == 100.0
    assert abs(fv.inter_packet_interval_ms - 100.0) < 0.01
    # Coefficient of variation should be very small for steady traffic
    assert fv.burstiness < 0.05
    # 10 packets / 5 sec = 120 ppm
    assert abs(fv.packets_per_minute - 120.0) < 1.0


def test_bursty_packets_have_high_burstiness():
    pkts = make_bursty_packets(n=10)
    fv = extract_features(pkts, 5.0)
    assert fv is not None
    assert fv.burstiness > 0.5, f"Expected burstiness > 0.5, got {fv.burstiness}"


def test_feature_list_length_matches_feature_names():
    from src.features import FEATURE_NAMES
    pkts = make_steady_packets(n=5, interval_ms=200.0)
    fv = extract_features(pkts, 5.0)
    assert len(fv.as_list()) == len(FEATURE_NAMES) == 4


def test_feature_distance_and_zscore():
    from src.features import FeatureVector
    a = FeatureVector(70, 5000, 12, 0.1)
    b = FeatureVector(72, 5050, 12, 0.15)
    assert feature_distance(a, b) > 0

    # zscore with zero std -> 0
    assert zscore(5.0, 5.0, 0.0) == 0.0
    assert zscore(7.0, 5.0, 1.0) == 2.0


def test_two_packets_minimum():
    pkts = [(1000.0, 80), (1000.5, 90)]
    fv = extract_features(pkts, 5.0)
    assert fv is not None
    assert fv.avg_packet_size == 85.0
    assert abs(fv.inter_packet_interval_ms - 500.0) < 0.01
