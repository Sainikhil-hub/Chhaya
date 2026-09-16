"""Pipeline orchestrator.

Wires capture -> feature extraction -> classification -> anomaly
detection -> alert sink. Runs on a background thread and exposes the
current state for the dashboard.

REQ-1 -> 22 are satisfied cooperatively by the modules this file uses.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable

import config
from src.capture import CapturedPacket, InProcessSource, LiveCaptureSource
from src.classifier import ChhayaClassifier, Prediction
from src.detector import Alert, AnomalyDetector
from src.features import FeatureVector, safe_extract
from src.utils import JsonListStore, get_logger, now_ts

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public state dataclass used by the dashboard
# ---------------------------------------------------------------------------
@dataclass
class DeviceState:
    source_ip: str
    last_features: FeatureVector | None = None
    last_prediction: Prediction | None = None
    status: str = "idle"           # "active" | "idle" | "rogue" | "spoofed"
    last_seen: float = 0.0
    sample_count: int = 0


@dataclass
class PipelineSnapshot:
    devices: dict[str, DeviceState]
    recent_alerts: list[Alert]
    system_status: str
    last_update: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "devices": {
                ip: {
                    "source_ip": ip,
                    "status": st.status,
                    "last_seen": st.last_seen,
                    "sample_count": st.sample_count,
                    "features": st.last_features.as_dict() if st.last_features else None,
                    "prediction": st.last_prediction.as_dict() if st.last_prediction else None,
                }
                for ip, st in self.devices.items()
            },
            "recent_alerts": [a.as_dict() for a in self.recent_alerts],
            "system_status": self.system_status,
            "last_update": self.last_update,
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
class Pipeline:
    def __init__(self, classifier: ChhayaClassifier,
                 source: InProcessSource | LiveCaptureSource | None = None,
                 alert_log: JsonListStore | None = None,
                 prediction_log: JsonListStore | None = None,
                 on_event: Callable[[str, dict], None] | None = None):
        """
        Parameters
        ----------
        classifier : ChhayaClassifier
            A trained (or pre-loaded) classifier.
        source : capture source or None
            Defaults to InProcessSource.
        on_event : callable or None
            Optional callback (event_name, payload) for the dashboard.
        """
        self.classifier = classifier
        self.source = source or InProcessSource()
        self.detector = AnomalyDetector()
        self.alert_log = alert_log or JsonListStore(config.ALERT_LOG_PATH)
        self.prediction_log = prediction_log or JsonListStore(config.PREDICTION_LOG_PATH)
        self.on_event = on_event

        # Per IP rolling buffer of (timestamp, size)
        self._pkts: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=2000)
        )
        # Per IP state
        self._devices: dict[str, DeviceState] = {}
        # Recent alerts (most recent first)
        self._recent_alerts: deque[Alert] = deque(maxlen=50)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._system_status = "idle"

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self.source.add_handler(self._on_packet)
        self.source.start()
        self._worker = threading.Thread(target=self._run_loop, daemon=True,
                                        name="chhaya-pipeline")
        self._worker.start()
        self._system_status = "capturing"
        log.info("Pipeline started")

    def stop(self) -> None:
        self._stop.set()
        if self._worker:
            self._worker.join(timeout=2.0)
        try:
            self.source.stop()
        except Exception:
            pass
        self._system_status = "idle"
        log.info("Pipeline stopped")

    # ------------------------------------------------------------------ ingress
    def _on_packet(self, pkt: CapturedPacket) -> None:
        with self._lock:
            self._pkts[pkt.src_ip].append((pkt.timestamp, pkt.size))

    # ------------------------------------------------------------------ main loop
    def _run_loop(self) -> None:
        while not self._stop.is_set():
            now = now_ts()
            # Snapshot the per-IP buffers
            with self._lock:
                buffers = {ip: list(buf) for ip, buf in self._pkts.items()}
            # Process each device independently
            for ip, pkts in buffers.items():
                if not pkts:
                    self._update_status(ip, "idle")
                    continue
                # Use only packets within the current window
                window_start = now - config.WINDOW_SECONDS
                recent = [p for p in pkts if p[0] >= window_start]
                if not recent:
                    self._update_status(ip, "idle")
                    continue
                features = safe_extract(recent, config.WINDOW_SECONDS)
                self._process_window(ip, features, now)
            time.sleep(config.CLASSIFICATION_INTERVAL)

    def _process_window(self, ip: str, features: FeatureVector, now: float) -> None:
        # Skip processing if there isn't enough real data in the window.
        if features.avg_packet_size == 0 and features.packets_per_minute == 0:
            self._update_status(ip, "idle")
            return
        prediction = self.classifier.predict(features)
        st = self._devices.setdefault(ip, DeviceState(source_ip=ip))
        st.last_features = features
        st.last_prediction = prediction
        st.last_seen = now
        st.sample_count += 1

        # Emit prediction event
        self._emit("prediction", {
            "source_ip": ip,
            "features": features.as_dict(),
            "prediction": prediction.as_dict(),
            "timestamp": now,
        })
        try:
            self.prediction_log.append({
                "source_ip": ip,
                "features": features.as_dict(),
                "prediction": prediction.as_dict(),
                "timestamp": now,
            })
        except Exception:
            log.exception("prediction_log append failed")

        # Spoofing detection first: a device with an established baseline
        # that suddenly drifts is an impersonation attempt (red). A
        # brand-new source IP has no baseline yet, so it falls through to
        # the rogue check below (amber).
        spoofing_alert = self.detector.update_and_detect_spoofing(
            ip, features, prediction)
        if spoofing_alert:
            self._handle_alert(spoofing_alert)
            self._update_status(ip, "spoofed")
            return

        # Rogue detection
        rogue_alert = self.detector.detect_rogue(ip, features, prediction)
        if rogue_alert:
            self._handle_alert(rogue_alert)
            self._update_status(ip, "rogue")
            return

        # Otherwise -> active
        self._update_status(ip, "active")

    # ------------------------------------------------------------------ helpers
    def _update_status(self, ip: str, status: str) -> None:
        st = self._devices.setdefault(ip, DeviceState(source_ip=ip))
        if st.status != status:
            st.status = status
            self._emit("status", {"source_ip": ip, "status": status})

    def _handle_alert(self, alert: Alert) -> None:
        with self._lock:
            self._recent_alerts.appendleft(alert)
        try:
            self.alert_log.append(alert.as_dict())
        except Exception:
            log.exception("alert_log append failed")
        self._emit("alert", alert.as_dict())

    def _emit(self, event: str, payload: dict) -> None:
        if self.on_event is None:
            return
        try:
            self.on_event(event, payload)
        except Exception:
            log.exception("on_event callback failed for %s", event)

    # ------------------------------------------------------------------ public API
    def snapshot(self) -> PipelineSnapshot:
        with self._lock:
            return PipelineSnapshot(
                devices={ip: st for ip, st in self._devices.items()},
                recent_alerts=list(self._recent_alerts),
                system_status=self._system_status,
                last_update=now_ts(),
            )

    def mark_alert_reviewed(self, alert_id: str) -> bool:
        with self._lock:
            for a in self._recent_alerts:
                if a.alert_id == alert_id:
                    a.reviewed = True
                    break
        # Persist
        self.alert_log.update(
            lambda item: item.get("alert_id") == alert_id,
            {"reviewed": True},
        )
        self._emit("alert_reviewed", {"alert_id": alert_id})
        return True
