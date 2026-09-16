"""Chhaya central configuration.

All tunable parameters live here so the pipeline, dashboard, and scripts
share a single source of truth (REQ: maintainability / configurable
parameters in a config file).
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
TRAINING_DIR = DATA_DIR / "training"
MODEL_DIR = DATA_DIR / "models"
LOG_DIR = DATA_DIR / "logs"

TRAINING_DATA_PATH = TRAINING_DIR / "training_data.csv"
MODEL_PATH = MODEL_DIR / "chhaya_rf.joblib"
ALERT_LOG_PATH = LOG_DIR / "alerts.json"
PREDICTION_LOG_PATH = LOG_DIR / "predictions.json"

for _d in (TRAINING_DIR, MODEL_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Pipeline timing
# ---------------------------------------------------------------------------
WINDOW_SECONDS = 12            # feature extraction window (REQ-5)
CLASSIFICATION_INTERVAL = 2.5 # seconds between predictions (REQ-18)
DASHBOARD_GRAPH_WINDOW = 60   # seconds of history kept on the live graph

# ---------------------------------------------------------------------------
# Classifier thresholds
# ---------------------------------------------------------------------------
# REQ-11: predictions below this are flagged as uncertain / rogue
CLASSIFIER_CONFIDENCE_THRESHOLD = 0.55
# REQ-10: target accuracy during offline eval (used only for warnings)
TARGET_ACCURACY = 0.85
# Random Forest hyperparameters
RF_N_ESTIMATORS = 200
RF_MAX_DEPTH = 12
RF_RANDOM_STATE = 42

# ---------------------------------------------------------------------------
# Spoofing detection
# ---------------------------------------------------------------------------
# REQ-15/16: per-device baseline + z-score threshold
SPOOFING_BASELINE_MIN_SAMPLES = 6     # distinct windows before judging
                                                # (camera: 6 bursts ~= 3 min)
# 4.0 plus a 2-window confirmation (below) keeps the false-alarm rate during
# normal operation near zero, while the calibrated spoofer drift (see
# SpooferSimulator) still produces z ~ 5-6 on every window.
SPOOFING_ZSCORE_THRESHOLD = 4.0       # |z| above this on any feature => suspect
SPOOFING_MIN_EXCEED_WINDOWS = 2      # consecutive suspect windows => spoofing
SPOOFING_LOOKBACK_WINDOWS = 20       # how many recent windows to keep per device
# Rogue detection uses a scale-aware (z-normalised) distance from the class
# prototypes below: legitimate windows score <= ~10, unknown/rogue traffic
# scores > ~100 on every profile.
ROGUE_ZDISTANCE_THRESHOLD = 30.0

# ---------------------------------------------------------------------------
# Known device profiles (used by simulator + training data generation)
# ---------------------------------------------------------------------------
# Each profile defines the behavioural fingerprint of a simulated IoT device.
# (avg_packet_size, inter_packet_interval_ms, burstiness, packets_per_minute)
DEVICE_PROFILES = {
    "sensor_node": {
        "label": "SensorNode",
        "description": "Environmental sensor - small steady packets every 5s",
        "avg_packet_size": 72,
        "packet_size_jitter": 12,
        "inter_packet_interval_ms": 5000,
        "interval_jitter_ms": 400,
        "burstiness": 0.08,   # jitter_ratio = 400/5000
    },
    "camera_stream": {
        "label": "CameraStream",
        "description": "Security camera - large bursts every 30s",
        "avg_packet_size": 1200,
        "packet_size_jitter": 180,
        "inter_packet_interval_ms": 33,     # ~30 fps inside a burst
        "interval_jitter_ms": 8,
        "burstiness": 0.24,   # jitter_ratio = 8/33
        "burst_packet_count": (8, 14),      # packets per burst
        "burst_interval_ms": 30_000,
    },
    "smart_switch": {
        "label": "SmartSwitch",
        "description": "Smart switch - tiny packets on event",
        "avg_packet_size": 32,
        "packet_size_jitter": 6,
        "inter_packet_interval_ms": 1800,
        "interval_jitter_ms": 900,
        "burstiness": 0.5,    # jitter_ratio = 900/1800
    },
    "rogue": {
        "label": "RogueDevice",
        "description": "Unknown device - mid-size packets at irregular intervals",
        "avg_packet_size": 600,
        "packet_size_jitter": 200,
        "inter_packet_interval_ms": 700,
        "interval_jitter_ms": 350,
        "burstiness": 0.5,
    },
}

KNOWN_DEVICE_LABELS = [k for k in DEVICE_PROFILES.keys() if k != "rogue"]


def get_known_centroids() -> dict[str, list[float]]:
    """Return one prototype feature vector per known device class.

    Used by the anomaly detector as a far-from-prototype reference when
    deciding whether an incoming device is rogue (REQ-12).

    IMPORTANT: prototypes must describe what one *pipeline window* looks
    like for each device, not the raw profile rate. The camera sends one
    8-14 packet burst every 30s, so a 12s window holds ~11 packets
    (~55 packets/min) - using the within-burst rate (~1818/min) here made
    every real camera window look "far from centroid" and flagged it rogue.
    """
    return {
        label: proto["mean"] for label, proto in get_known_class_protos().items()
    }


def get_known_class_protos() -> dict[str, dict[str, list[float]]]:
    """Per-class feature prototypes: mean and spread (std) of one window.

    The means match pipeline window semantics (see get_known_centroids);
    the spreads come from the training corpus / simulator variance and are
    used to z-normalise the rogue distance so features on very different
    scales (packet bytes vs interval ms) contribute proportionally.
    """
    return {
        "sensor_node": {
            "mean": [72.0, 5000.0, 12.0, 0.08],
            "std": [6.8, 233.0, 0.6, 0.08],
        },
        "camera_stream": {
            "mean": [1200.0, 33.0, 55.0, 0.24],
            "std": [54.0, 4.0, 8.0, 0.09],
        },
        "smart_switch": {
            "mean": [32.0, 1800.0, 33.0, 0.5],
            "std": [3.4, 518.0, 11.7, 0.08],
        },
    }

# ---------------------------------------------------------------------------
# Simulator network
# ---------------------------------------------------------------------------
SIMULATOR_TARGET_IP = "127.0.0.1"
SIMULATOR_TARGET_PORT = 9999
# Three virtual source IPs in 127.0.0.0/8 (loopback) so each simulator
# instance has a distinct identity without needing extra NICs.
SIMULATOR_SOURCE_IPS = {
    "sensor_node":   "127.0.0.11",
    "camera_stream": "127.0.0.12",
    "smart_switch":  "127.0.0.13",
    "rogue":         "127.0.0.20",
    "spoofer":       "127.0.0.21",
}

# ---------------------------------------------------------------------------
# Live capture (used when ESP8266 boards are attached)
# ---------------------------------------------------------------------------
CAPTURE_INTERFACE = os.environ.get("CHHAYA_IFACE", None)  # auto if None
CAPTURE_BPF = "udp dst port 9999"   # only packets sent by the boards to Chhaya
CAPTURE_PACKET_TIMEOUT = 1.0    # seconds (scapy sniff timeout)
# Port the UDP capture source ("--mode udp") binds on the capture laptop.
# The ESP8266 firmware sends to this port (TARGET_PORT in chhaya_config.h).
CAPTURE_LISTEN_PORT = 9999

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000
SECRET_KEY = os.environ.get("CHHAYA_SECRET", "chhaya-demo-not-for-prod")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("CHHAYA_LOG", "INFO")