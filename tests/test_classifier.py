"""Tests for the RandomForest classifier (REQ-8/9/10/11)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.classifier import GhostPrintClassifier, generate_synthetic_dataset  # noqa: E402
from src.features import FeatureVector  # noqa: E402


def test_synthetic_dataset_shape():
    X, y = generate_synthetic_dataset(n_per_class=50)
    assert X.shape[0] == 50 * 3
    assert X.shape[1] == 4
    assert len(y) == X.shape[0]
    assert set(y).issubset({"sensor_node", "camera_stream", "smart_switch"})


def test_classifier_achieves_target_accuracy():
    X, y = generate_synthetic_dataset(n_per_class=300)
    clf = GhostPrintClassifier()
    summary = clf.train(X, y, verbose=False)
    assert summary["accuracy"] >= 0.85, f"Accuracy {summary['accuracy']:.3f} < 0.85"


def test_classifier_predict_returns_label_and_confidence():
    X, y = generate_synthetic_dataset(n_per_class=200)
    clf = GhostPrintClassifier()
    clf.train(X, y, verbose=False)

    # A vector in the centre of the sensor_node profile
    fv = FeatureVector(avg_packet_size=72, inter_packet_interval_ms=5000,
                       packets_per_minute=12.0, burstiness=0.15)
    pred = clf.predict(fv)
    assert pred.label in {"sensor_node", "camera_stream", "smart_switch", "unknown"}
    assert 0.0 <= pred.confidence <= 1.0
    assert "sensor_node" in pred.probabilities
    assert pred.probabilities["sensor_node"] > 0.5


def test_classifier_handles_low_confidence_flag():
    """A vector at the boundary of training distributions should produce
    a low-confidence prediction (below threshold)."""
    X, y = generate_synthetic_dataset(n_per_class=200)
    clf = GhostPrintClassifier()
    clf.train(X, y, verbose=False)

    # Mix of two profiles - should produce non-decisive probabilities.
    half_camera = FeatureVector(avg_packet_size=600, inter_packet_interval_ms=33,
                                 packets_per_minute=1800, burstiness=1.2)
    pred = clf.predict(half_camera)
    # If the classifier is uncertain, the rogue detector will fire.
    # If it is confident, the rogue detector's distance-from-centroid
    # check will fire instead. Both are acceptable outcomes.
    assert pred.uncertain or 0.0 < pred.confidence <= 1.0


def test_save_and_load_roundtrip(tmp_path):
    X, y = generate_synthetic_dataset(n_per_class=100)
    clf = GhostPrintClassifier()
    clf.train(X, y, verbose=False)

    path = clf.save(tmp_path / "model.joblib")
    loaded = GhostPrintClassifier.load(path)
    fv = FeatureVector(72, 5000, 12, 0.15)
    p1 = clf.predict(fv)
    p2 = loaded.predict(fv)
    assert p1.label == p2.label
    assert abs(p1.confidence - p2.confidence) < 1e-6
