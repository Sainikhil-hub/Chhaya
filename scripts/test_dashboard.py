"""Quick smoke test for the dashboard endpoints."""
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.capture import make_source
from src.classifier import ChhayaClassifier
from src.pipeline import Pipeline
from src.traffic_simulator import SimulatorOrchestrator
from dashboard.app import create_app


def main() -> None:
    clf = ChhayaClassifier.load()
    src = make_source("inprocess")
    pipe = Pipeline(classifier=clf, source=src)
    sim = SimulatorOrchestrator(on_packet=src.feed)
    sim.start()
    pipe.start()

    try:
        app, _socketio = create_app(pipeline=pipe, simulator=sim, async_mode="threading")
        with app.test_client() as c:
            r = c.get("/")
            assert r.status_code == 200
            assert b"Chhaya" in r.data
            print(f"GET /: {r.status_code} ({len(r.data)} bytes)")

            r = c.get("/api/health")
            assert r.status_code == 200
            print(f"GET /api/health: {r.json}")

            r = c.get("/api/state")
            assert r.status_code == 200
            data = r.json
            print(f"GET /api/state: devices={len(data['devices'])}, alerts={len(data['recent_alerts'])}, status={data['system_status']}")

            r = c.post("/api/sim/rogue", json={"enabled": True})
            assert r.status_code == 200
            print(f"POST /api/sim/rogue: {r.json}")

            r = c.post("/api/sim/spoofer", json={"enabled": True, "target": "camera_stream"})
            assert r.status_code == 200
            print(f"POST /api/sim/spoofer: {r.json}")

        print("OK - dashboard works.")
    finally:
        pipe.stop()
        sim.stop()


if __name__ == "__main__":
    main()