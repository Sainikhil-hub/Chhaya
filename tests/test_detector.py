"""Tests for the anomaly detector (REQ-12/13, 15/16/17)."""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from src.classifier import ChhayaClassifier, generate_synthetic_dataset  # noqa: E402
from src.detector import AnomalyDetector  # noqa: E402
from src.features import FeatureVector  # noqa: E402


def _make_classifier():
    X, y = generate_synthetic_dataset(n_per_class=200)
    clf = ChhayaClassifier()
    clf.train(X, y, verbose=False)
    return clf


def test_rogue_detected_on_low_confidence():
    clf = _make_classifier()
    det = AnomalyDetector()
    bogus = FeatureVector(avg_packet_size=9999, inter_packet_interval_ms=1,
                          packets_per_minute=60_000, burstiness=10.0)
    pred = clf.predict(bogus)
    alert = det.detect_rogue("10.0.0.99", bogus, pred)
    assert alert is not None
    assert alert.type == "rogue"
    assert alert.source_ip == "10.0.0.99"


def test_rogue_not_alerted_for_known_profile():
    clf = _make_classifier()
    det = AnomalyDetector()
    fv = FeatureVector(avg_packet_size=72, inter_packet_interval_ms=5000,
                       packets_per_minute=12.0, burstiness=0.15)
    pred = clf.predict(fv)
    alert = det.detect_rogue("10.0.0.10", fv, pred)
    assert alert is None


def test_spoofing_detected_after_baseline_warmup():
    clf = _make_classifier()
    det = AnomalyDetector()
    # Feed realistic (slightly jittered) sensor_node traffic to build the
    # baseline - identical windows would give the baseline zero variance.
    rng = random.Random(42)
    for _ in range(15):
        fv = FeatureVector(avg_packet_size=72 + rng.uniform(-4, 4),
                           inter_packet_interval_ms=5000 + rng.uniform(-150, 150),
                           packets_per_minute=12.0 + rng.uniform(-0.8, 0.8),
                           burstiness=0.15 + rng.uniform(-0.04, 0.04))
        det.update_and_detect_spoofing("10.0.0.10", fv, clf.predict(fv))
    # Inject a packet that still looks like sensor_node on average
    # (size and interval match) but has a wildly different burstiness,
    # so the classifier is confident but the z-score spikes. A single
    # suspect window is not enough - the second consecutive one alerts.
    fake = FeatureVector(avg_packet_size=72, inter_packet_interval_ms=5000,
                         packets_per_minute=12.0, burstiness=2.0)
    pred = clf.predict(fake)
    assert not pred.uncertain  # needs to be confident for spoofing check
    first = det.update_and_detect_spoofing("10.0.0.10", fake, pred)
    assert first is None  # one window is not confirmation
    alert = det.update_and_detect_spoofing("10.0.0.10", fake, pred)
    assert alert is not None
    assert alert.type == "spoofing"
    assert alert.severity == "critical"


def test_spoofing_attack_does_not_poison_baseline():
    """Sustained drift must keep alerting: attack windows are never folded
    into the baseline (otherwise the detector would absorb the attack and
    clear itself mid-impersonation)."""
    clf = _make_classifier()
    det = AnomalyDetector()
    rng = random.Random(7)
    for _ in range(15):
        fv = FeatureVector(avg_packet_size=72 + rng.uniform(-4, 4),
                           inter_packet_interval_ms=5000 + rng.uniform(-150, 150),
                           packets_per_minute=12.0 + rng.uniform(-0.8, 0.8),
                           burstiness=0.15 + rng.uniform(-0.04, 0.04))
        det.update_and_detect_spoofing("10.0.0.10", fv, clf.predict(fv))
    baseline = det.baseline_snapshot()["10.0.0.10"]

    alerts = 0
    for _ in range(10):
        drifted = FeatureVector(avg_packet_size=72, inter_packet_interval_ms=4400,
                                packets_per_minute=13.0, burstiness=0.15)
        alert = det.update_and_detect_spoofing(
            "10.0.0.10", drifted, clf.predict(drifted))
        if alert is not None:
            alerts += 1

    # Cooldown (10s) allows at most one alert in this tight loop, but the
    # baseline must be untouched by the drifted windows so the next alert
    # after the cooldown is still guaranteed.
    assert alerts >= 1
    assert det.baseline_snapshot()["10.0.0.10"] == baseline


def test_spoofing_baseline_learns_normal_windows():
    """Normal windows keep folding into the baseline (slow drift tracking)."""
    clf = _make_classifier()
    det = AnomalyDetector()
    rng = random.Random(3)
    # Jittered so each window is distinct (identical consecutive windows
    # are deduplicated before they reach the baseline).
    for _ in range(15):
        fv = FeatureVector(avg_packet_size=72 + rng.uniform(-4, 4),
                           inter_packet_interval_ms=5000 + rng.uniform(-150, 150),
                           packets_per_minute=12.0 + rng.uniform(-0.8, 0.8),
                           burstiness=0.15 + rng.uniform(-0.04, 0.04))
        det.update_and_detect_spoofing("10.0.0.10", fv, clf.predict(fv))
    baseline_before = det.baseline_snapshot()["10.0.0.10"]["avg_packet_size"][0]
    # A gentle shift that stays within the z-score threshold.
    for _ in range(5):
        shifted = FeatureVector(avg_packet_size=74, inter_packet_interval_ms=4950,
                                packets_per_minute=12.2, burstiness=0.16)
        alert = det.update_and_detect_spoofing(
            "10.0.0.10", shifted, clf.predict(shifted))
        assert alert is None
    # The shifted windows were folded in, moving the baseline mean upward.
    stats = det.baseline_snapshot()["10.0.0.10"]
    assert stats["avg_packet_size"][0] > baseline_before


def test_spoofing_no_alert_during_warmup():
    clf = _make_classifier()
    det = AnomalyDetector()
    fv = FeatureVector(avg_packet_size=72, inter_packet_interval_ms=5000,
                       packets_per_minute=12.0, burstiness=0.15)
    alert = det.update_and_detect_spoofing("10.0.0.10", fv, clf.predict(fv))
    assert alert is None  # warm-up period
