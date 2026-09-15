"""Run the full GhostPrint demo:

* starts the software IoT simulator (3 known devices + spoofer)
* starts the capture + ML pipeline
* starts the Flask-SocketIO dashboard

Usage:
    python scripts/run_demo.py                       # default in-process demo
    python scripts/run_demo.py --mode live           # try scapy live capture
    python scripts/run_demo.py --no-simulator        # only pipeline + dashboard
    python scripts/run_demo.py --regen-model         # retrain the model first
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from src.capture import InProcessSource, make_source  # noqa: E402
from src.classifier import GhostPrintClassifier  # noqa: E402
from src.pipeline import Pipeline  # noqa: E402
from src.traffic_simulator import SimulatorOrchestrator  # noqa: E402
from src.utils import configure_logging, get_logger  # noqa: E402

log = get_logger(__name__)


def ensure_model() -> GhostPrintClassifier:
    """Load the trained model, or train a fresh one if none exists."""
    if config.MODEL_PATH.exists():
        try:
            return GhostPrintClassifier.load()
        except Exception as e:
            log.warning("Failed to load model (%s); retraining.", e)
    log.info("No trained model found - training a fresh one...")
    from src.classifier import generate_synthetic_dataset
    import pandas as pd
    from src.features import FEATURE_NAMES
    X, y = generate_synthetic_dataset(n_per_class=300)
    clf = GhostPrintClassifier()
    clf.train(X, y)
    clf.save()
    # Also save the CSV for the record
    df = pd.DataFrame(X, columns=list(FEATURE_NAMES))
    df.insert(0, "label", y)
    df.to_csv(config.TRAINING_DATA_PATH, index=False)
    return clf


def main() -> None:
    p = argparse.ArgumentParser(description="Run the GhostPrint demo.")
    p.add_argument("--mode", choices=["inprocess", "live", "udp"], default="inprocess",
                   help="Capture mode (inprocess = simulator-friendly; udp = real "
                        "ESP8266 boards sending to this laptop, no Npcap needed; "
                        "live = scapy sniffing)")
    p.add_argument("--host", default=config.DASHBOARD_HOST)
    p.add_argument("--port", type=int, default=config.DASHBOARD_PORT)
    p.add_argument("--no-simulator", action="store_true",
                   help="Skip starting the simulator (use only if you have ESP8266 boards)")
    p.add_argument("--regen-model", action="store_true",
                   help="Retrain the model before starting")
    p.add_argument("--interface", default=None,
                   help="Network interface for live capture (e.g. 'Wi-Fi')")
    args = p.parse_args()

    configure_logging()

    # 1. Model
    if args.regen_model:
        config.MODEL_PATH.unlink(missing_ok=True)
    classifier = ensure_model()

    # 2. Capture source
    source = make_source(mode=args.mode, interface=args.interface)

    # 3. Pipeline
    pipeline = Pipeline(classifier=classifier, source=source)

    # 4. Simulator (if in-process)
    simulator: SimulatorOrchestrator | None = None
    if args.mode == "inprocess" and not args.no_simulator:
        if not isinstance(source, InProcessSource):
            log.warning("Source is not InProcessSource; simulator disabled.")
        else:
            simulator = SimulatorOrchestrator(on_packet=source.feed)
            simulator.start()

    # 5. Start pipeline
    pipeline.start()

    # 6. Start Flask dashboard in the main thread
    # Import lazily so pipeline can run standalone without flask.
    from dashboard.app import create_app
    app, socketio = create_app(pipeline=pipeline, simulator=simulator)
    log.info("=" * 70)
    log.info(" GhostPrint dashboard ready - open http://%s:%d",
             args.host, args.port)
    log.info("=" * 70)

    try:
        socketio.run(app, host=args.host, port=args.port,
                     allow_unsafe_werkzeug=True, debug=False)
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        pipeline.stop()
        if simulator:
            simulator.stop()


if __name__ == "__main__":
    main()
