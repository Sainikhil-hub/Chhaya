"""Rogue device + spoofing detection.

REQ-12/13/14: rogue device alert when a feature vector is too far from
any known class (or the classifier reports low confidence).

REQ-15/16/17: spoofing alert when a device's features match a known
class nominally but deviate beyond a statistical threshold from that
device's running baseline.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque

import config
from src.classifier import Prediction
from src.features import FEATURE_NAMES, FeatureVector, zscore
from src.utils import get_logger

log = get_logger(__name__)


@dataclass
class Alert:
    alert_id: str
    type: str            # "rogue" | "spoofing"
    severity: str        # "warning" | "critical"
    source_ip: str
    message: str
    timestamp: float
    reviewed: bool = False
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "type": self.type,
            "severity": self.severity,
            "source_ip": self.source_ip,
            "message": self.message,
            "timestamp": self.timestamp,
            "reviewed": self.reviewed,
            "extra": self.extra,
        }


class AnomalyDetector:
    """Tracks per-device baselines and emits alerts when fingerprint
    deviates unexpectedly.

    Known class prototypes (mean + spread) are loaded once from
    config.get_known_class_protos() so the rogue detector has a reference
    even before any live traffic has been observed.
    """

    def __init__(self, known_protos: dict[str, dict[str, list[float]]] | None = None):
        # Per source IP: rolling window of recent feature vectors
        self._history: dict[str, Deque[list[float]]] = defaultdict(
            lambda: deque(maxlen=config.SPOOFING_LOOKBACK_WINDOWS)
        )
        # Per source IP: running mean / std per feature (spoofing baseline)
        self._baseline: dict[str, dict[str, tuple[float, float]]] = {}
        # Known class prototypes (for rogue detection)
        self._known_protos: dict[str, dict[str, list[float]]] = (
            known_protos if known_protos is not None
            else config.get_known_class_protos()
        )
        # Cooldown so we don't spam alerts
        self._last_alert_ts: dict[tuple[str, str], float] = {}
        # Per source IP: how many consecutive windows exceeded the spoofing
        # z-score threshold (a single spike is not enough evidence).
        self._exceed_streak: dict[str, int] = defaultdict(int)
        # Per source IP: when it was last flagged rogue by the distance
        # rule (spoofing is suppressed for genuinely unknown devices).
        self._rogue_flagged: dict[str, float] = {}
        self._alert_seq = 0

    # ------------------------------------------------------------------ rogue
    def detect_rogue(self, source_ip: str, features: FeatureVector,
                     prediction: Prediction) -> Alert | None:
        """A device is rogue if the classifier is uncertain OR the feature
        vector is far from EVERY known class prototype.

        Distance is z-normalised per feature (using each class's expected
        spread), so packet-size bytes and interval milliseconds contribute
        proportionally instead of the raw byte/ms scale dominating."""
        reasons = []
        if prediction.uncertain:
            reasons.append(
                f"classifier confidence {prediction.confidence:.2f} "
                f"below threshold {config.CLASSIFIER_CONFIDENCE_THRESHOLD}"
            )

        # Z-distance-from-prototype check: rogue iff far from ALL classes.
        if self._known_protos:
            dists = {}
            for label, proto in self._known_protos.items():
                mean, std = proto["mean"], proto["std"]
                dists[label] = sum(
                    ((a - m) / (s or 1e-9)) ** 2
                    for a, m, s in zip(features.as_list(), mean, std)
                ) ** 0.5
            min_label = min(dists, key=dists.get)
            min_dist = dists[min_label]
            if min_dist > config.ROGUE_ZDISTANCE_THRESHOLD:
                reasons.append(
                    f"feature vector far from every known device profile "
                    f"(closest='{min_label}' z-distance={min_dist:.0f})"
                )
                # A device that is genuinely far from every known profile is
                # an unknown device - spoofing analysis does not apply to it.
                self._rogue_flagged[source_ip] = time.time()

        if not reasons:
            return None

        if self._cooldown_active(source_ip, "rogue"):
            return None

        self._alert_seq += 1
        return Alert(
            alert_id=f"alert-{self._alert_seq}",
            type="rogue",
            severity="warning",
            source_ip=source_ip,
            message="Unknown / rogue device detected on the network",
            timestamp=_now(),
            extra={"reasons": reasons, "prediction": prediction.as_dict()},
        )

    # --------------------------------------------------------------- spoofing
    def update_and_detect_spoofing(self, source_ip: str, features: FeatureVector,
                                   prediction: Prediction) -> Alert | None:
        """Maintain a rolling baseline per source IP and flag spoofing when
        a known device's features drift beyond a z-score threshold.

        The baseline is *gated*: windows whose z-scores exceed the threshold
        are treated as attack evidence and are never folded into the
        baseline. Without this, a sustained impersonation would be absorbed
        into the reference statistics within a few windows and the alert
        would silently clear itself mid-attack.
        """
        vec = features.as_list()
        hist = self._history[source_ip]

        # A bursty device's packets stay inside the lookback window for
        # several pipeline ticks, producing several IDENTICAL windows from
        # one burst. Re-processing them would (a) fake extra samples,
        # shrinking the baseline std until the next real burst explodes
        # the z-score, and (b) double-count one burst toward the 2-window
        # confirmation. Skip windows identical to the previous one.
        if hist and list(hist[-1]) == vec:
            return None

        # Spoofing analysis assumes an established, known device. If this
        # source was recently judged far from every known profile, it is an
        # unknown device - the rogue path owns it, don't double-report.
        last_rogue = self._rogue_flagged.get(source_ip, 0.0)
        if time.time() - last_rogue < 60.0:
            return None

        # Warm-up: build the baseline from the first distinct windows.
        if len(hist) < config.SPOOFING_BASELINE_MIN_SAMPLES:
            hist.append(vec)
            if len(hist) < config.SPOOFING_BASELINE_MIN_SAMPLES:
                return None
            self._baseline[source_ip] = _mean_std_per_feature(list(hist))
            return None

        if prediction.uncertain:
            # Unreliable evidence: neither alert on it nor learn from it.
            return None

        stats = self._baseline[source_ip]
        z_by_feature = {
            name: zscore(float(v), stats[name][0], stats[name][1])
            for name, v in zip(FEATURE_NAMES, vec)
        }
        max_abs_z = max(abs(z) for z in z_by_feature.values())
        if max_abs_z <= config.SPOOFING_ZSCORE_THRESHOLD:
            # Normal window: fold it into the baseline and reset the streak.
            self._exceed_streak[source_ip] = 0
            self._history[source_ip].append(vec)
            self._baseline[source_ip] = _mean_std_per_feature(
                list(self._history[source_ip]))
            return None

        # Suspect window: do NOT fold it into the baseline (a sustained
        # impersonation must not reshape its own reference), and require
        # confirmation from consecutive windows before alerting.
        self._exceed_streak[source_ip] += 1
        if self._exceed_streak[source_ip] < config.SPOOFING_MIN_EXCEED_WINDOWS:
            return None

        if self._cooldown_active(source_ip, "spoofing"):
            return None

        self._alert_seq += 1
        outlier = max(z_by_feature.items(), key=lambda kv: abs(kv[1]))
        return Alert(
            alert_id=f"alert-{self._alert_seq}",
            type="spoofing",
            severity="critical",
            source_ip=source_ip,
            message=(
                f"Possible spoofing: '{source_ip}' is impersonating "
                f"'{prediction.label}' but feature '{outlier[0]}' has drifted "
                f"(z={outlier[1]:.2f})"
            ),
            timestamp=_now(),
            extra={
                "impostor_label": prediction.label,
                "max_zscore": round(max_abs_z, 3),
                "z_by_feature": {k: round(v, 3) for k, v in z_by_feature.items()},
            },
        )

    # ---------------------------------------------------------------- helpers
    def baseline_snapshot(self) -> dict[str, dict[str, tuple[float, float]]]:
        return {k: {f: tuple(v) for f, v in stats.items()}
                for k, stats in self._baseline.items()}

    def _cooldown_active(self, source_ip: str, alert_type: str,
                         cooldown_sec: float = 10.0) -> bool:
        import time
        key = (source_ip, alert_type)
        last = self._last_alert_ts.get(key, 0)
        if time.time() - last < cooldown_sec:
            return True
        self._last_alert_ts[key] = time.time()
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mean_std_per_feature(rows: list[list[float]]) -> dict[str, tuple[float, float]]:
    n = len(rows)
    if n == 0:
        return {f: (0.0, 0.0) for f in FEATURE_NAMES}
    means = [sum(r[i] for r in rows) / n for i in range(len(FEATURE_NAMES))]
    stds = []
    for i in range(len(FEATURE_NAMES)):
        m = means[i]
        var = sum((r[i] - m) ** 2 for r in rows) / n
        stds.append(var ** 0.5)
    return {f: (means[i], stds[i]) for i, f in enumerate(FEATURE_NAMES)}


def _now() -> float:
    import time
    return time.time()
