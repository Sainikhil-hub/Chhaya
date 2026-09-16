"""Random Forest classifier for IoT device identification.

REQ-8/9/10/11: trained Random Forest that returns a device label and
confidence score, with uncertain predictions flagged below a threshold.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

import config
from src.features import FEATURE_NAMES, FeatureVector
from src.utils import get_logger

log = get_logger(__name__)


@dataclass
class Prediction:
    label: str              # predicted device class ("sensor_node") or "unknown"
    confidence: float       # 0..1
    uncertain: bool         # True if below CLASSIFIER_CONFIDENCE_THRESHOLD
    probabilities: dict[str, float]  # per-class probabilities

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "uncertain": self.uncertain,
            "probabilities": {k: round(v, 4) for k, v in self.probabilities.items()},
        }


class ChhayaClassifier:
    """Wraps a trained Random Forest and provides a clean predict API."""

    def __init__(self, model: RandomForestClassifier | None = None):
        self.model: RandomForestClassifier | None = model
        self.classes: list[str] = list(config.KNOWN_DEVICE_LABELS)

    # ------------------------------------------------------------------ train
    def train(self, X: np.ndarray, y: np.ndarray, *, verbose: bool = True) -> dict:
        """Fit the model and return an evaluation summary."""
        if len(X) < 10:
            raise ValueError("Need at least 10 training samples to fit a Random Forest.")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=config.RF_RANDOM_STATE, stratify=y,
        )

        self.model = RandomForestClassifier(
            n_estimators=config.RF_N_ESTIMATORS,
            max_depth=config.RF_MAX_DEPTH,
            random_state=config.RF_RANDOM_STATE,
            n_jobs=-1,
        )
        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

        self.classes = list(self.model.classes_)

        if verbose:
            log.info("Trained Random Forest on %d samples (test acc=%.3f)",
                     len(X), acc)
            if acc < config.TARGET_ACCURACY:
                log.warning("Accuracy %.3f is below target %.3f (REQ-10) - "
                            "consider regenerating training data.",
                            acc, config.TARGET_ACCURACY)

        return {"accuracy": acc, "report": report, "n_train": len(X_train), "n_test": len(X_test)}

    # ------------------------------------------------------------------ predict
    def predict(self, features: FeatureVector) -> Prediction:
        if self.model is None:
            raise RuntimeError("Classifier has not been trained or loaded.")

        x = np.array(features.as_list(), dtype=float).reshape(1, -1)
        proba = self.model.predict_proba(x)[0]
        idx = int(np.argmax(proba))
        label = str(self.model.classes_[idx])
        confidence = float(proba[idx])

        uncertain = confidence < config.CLASSIFIER_CONFIDENCE_THRESHOLD
        probabilities = {str(c): float(p) for c, p in zip(self.model.classes_, proba)}

        return Prediction(
            label=label if not uncertain else "unknown",
            confidence=confidence,
            uncertain=uncertain,
            probabilities=probabilities,
        )

    # ------------------------------------------------------------------ persist
    def save(self, path: Path | None = None) -> Path:
        if self.model is None:
            raise RuntimeError("Nothing to save - model is not trained.")
        path = Path(path or config.MODEL_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "classes": self.classes}, path)
        log.info("Saved model to %s", path)
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "ChhayaClassifier":
        path = Path(path or config.MODEL_PATH)
        if not path.exists():
            raise FileNotFoundError(
                f"No trained model at {path}. Run scripts/train_model.py first."
            )
        bundle = joblib.load(path)
        inst = cls(model=bundle["model"])
        inst.classes = list(bundle.get("classes", config.KNOWN_DEVICE_LABELS))
        log.info("Loaded model from %s (classes=%s)", path, inst.classes)
        return inst


# ---------------------------------------------------------------------------
# Synthetic training data generator (used by scripts/generate_training_data.py)
# ---------------------------------------------------------------------------
def _jitter(value: float, jitter: float, rng: random.Random) -> float:
    """Symmetric uniform jitter around a value."""
    if jitter <= 0:
        return value
    return max(0.0, value + rng.uniform(-jitter, jitter))


def generate_synthetic_sample(profile_key: str, rng: random.Random) -> list[float]:
    """Generate one synthetic feature vector from a device profile.

    The values are jittered around the profile's nominal parameters so the
    trained classifier learns a region of feature space rather than a single
    point, which makes it robust to real-world noise.

    NOTE: burstiness is derived from the *interval jitter* (coefficient of
    variation of inter-packet intervals) so the synthetic distribution
    matches what ``src.features.extract_features`` actually computes from
    a packet trace. The profile's nominal ``burstiness`` field is used as
    a hint when present but otherwise computed here.
    """
    prof = config.DEVICE_PROFILES[profile_key]
    avg_size = _jitter(prof["avg_packet_size"], prof["packet_size_jitter"], rng)
    avg_interval = max(1.0, _jitter(prof["inter_packet_interval_ms"],
                                    prof["interval_jitter_ms"], rng))

    # Burstiness = std / mean of inter-packet intervals. We approximate
    # this from the configured interval jitter.
    base_burst = prof.get("burstiness")
    if base_burst is not None and base_burst > 0:
        burstiness = max(0.0, base_burst + rng.uniform(-0.15, 0.15))
    else:
        # Derive from interval jitter
        jitter_ratio = prof["interval_jitter_ms"] / max(1.0, prof["inter_packet_interval_ms"])
        burstiness = max(0.0, jitter_ratio + rng.uniform(-0.1, 0.1))

    # Packets per minute derived from the interval so the four features
    # remain internally consistent.
    if avg_interval > 0:
        ppm = 60_000.0 / avg_interval
    else:
        ppm = 0.0

    return [round(avg_size, 2), round(avg_interval, 2), round(ppm, 2), round(burstiness, 3)]


def generate_synthetic_dataset(n_per_class: int = 300,
                               seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Generate (X, y) for training. Returns numpy arrays."""
    rng = random.Random(seed)
    X_rows: list[list[float]] = []
    y: list[str] = []
    for label in config.KNOWN_DEVICE_LABELS:
        for _ in range(n_per_class):
            X_rows.append(generate_synthetic_sample(label, rng))
            y.append(label)
    X = np.array(X_rows, dtype=float)
    y = np.array(y, dtype=object)
    return X, y
