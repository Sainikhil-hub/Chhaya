"""End-to-end smoke test for GhostPrint.

Run this before the showcase to confirm the full demo flow works:

    python scripts/smoke_test.py

Takes ~75 seconds and exits non-zero if any phase fails.

Phase 1: three simulated devices are identified, with no alerts.
Phase 2: the rogue device triggers an amber "rogue" alert.
Phase 3: the spoofer (impersonating SensorNode) triggers a red
         "spoofing" alert within seconds of being enabled.
"""
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from src.capture import make_source  # noqa: E402
from src.classifier import GhostPrintClassifier  # noqa: E402
from src.pipeline import Pipeline  # noqa: E402
from src.traffic_simulator import SimulatorOrchestrator  # noqa: E402

IPS = config.SIMULATOR_SOURCE_IPS
EXPECTED_LABELS = {
    IPS["sensor_node"]: "sensor_node",
    IPS["camera_stream"]: "camera_stream",
    IPS["smart_switch"]: "smart_switch",
}


def main() -> int:
    clf = GhostPrintClassifier.load()
    src = make_source("inprocess")
    pipe = Pipeline(classifier=clf, source=src)
    sim = SimulatorOrchestrator(on_packet=src.feed)
    sim.start()
    pipe.start()

    failures = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" - {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    try:
        # ---------------------------------------------------------- Phase 1
        print("=== Phase 1: normal traffic (25s) ===")
        time.sleep(25)
        snap = pipe.snapshot()
        for ip, label in EXPECTED_LABELS.items():
            st = snap.devices.get(ip)
            pred = st.last_prediction.as_dict() if st and st.last_prediction else None
            got = pred["label"] if pred else None
            conf = pred["confidence"] if pred else 0.0
            check(f"{label} identified", got == label,
                  f"got={got}, conf={conf:.2f}" if pred else "no prediction yet")
        check("no alerts during normal traffic",
              not [a for a in snap.recent_alerts],
              f"{len(snap.recent_alerts)} alert(s)" if snap.recent_alerts else "")

        # ---------------------------------------------------------- Phase 2
        print("=== Phase 2: enabling rogue device ===")
        sim.enable_rogue()
        time.sleep(10)
        snap = pipe.snapshot()
        rogue_alerts = [a for a in snap.recent_alerts
                        if a.type == "rogue" and a.source_ip == IPS["rogue"]]
        check("rogue device flagged (amber alert)", len(rogue_alerts) > 0)

        # ---------------------------------------------------------- Phase 3
        print("=== Phase 3: enabling spoofer (impersonating SensorNode) ===")
        sim.disable_rogue()
        sim.enable_spoofer(target="sensor_node")
        time.sleep(20)
        snap = pipe.snapshot()
        spoof_alerts = [a for a in snap.recent_alerts
                        if a.type == "spoofing" and a.source_ip == IPS["sensor_node"]]
        check("spoofing detected (red critical alert)", len(spoof_alerts) > 0)
        if spoof_alerts:
            a = spoof_alerts[0]
            check("alert severity is critical", a.severity == "critical",
                  a.message[:90])
            check("alert names the impersonated device",
                  "sensor_node" in a.message, a.message[:90])

    finally:
        pipe.stop()
        sim.stop()

    print()
    if failures:
        print(f"SMOKE TEST FAILED: {len(failures)} check(s) failed: {failures}")
        return 1
    print("SMOKE TEST PASSED - demo flow is healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
