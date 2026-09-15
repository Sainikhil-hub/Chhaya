"""Flask + SocketIO dashboard for GhostPrint.

Exposes:
* GET  /                       -> main dashboard
* GET  /api/state              -> current pipeline snapshot
* POST /api/alerts/<id>/review -> mark an alert reviewed
* POST /api/sim/rogue          -> toggle rogue device
* POST /api/sim/spoofer        -> toggle spoofer (with target profile)

The pipeline emits events via its ``on_event`` callback which we
forward to the connected browsers via SocketIO.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

import config
from src.pipeline import Pipeline
from src.traffic_simulator import SimulatorOrchestrator
from src.utils import configure_logging, get_logger

log = get_logger(__name__)


def create_app(pipeline: Pipeline, simulator: Optional[SimulatorOrchestrator] = None,
               *, async_mode: str = "threading") -> tuple[Flask, SocketIO]:
    """Create the Flask + SocketIO app and wire it to the pipeline.

    Returns the (app, socketio) tuple so the caller can run it.
    """
    configure_logging()
    app = Flask(__name__,
                template_folder=str(Path(__file__).parent / "templates"),
                static_folder=str(Path(__file__).parent / "static"))
    app.config["SECRET_KEY"] = config.SECRET_KEY

    socketio = SocketIO(app, cors_allowed_origins="*", async_mode=async_mode,
                        logger=False, engineio_logger=False)

    # ---- Pipeline -> SocketIO bridge ---------------------------------------
    def _on_event(event: str, payload: dict) -> None:
        socketio.emit(event, payload)

    pipeline.on_event = _on_event
    # Push initial snapshots to all clients on connect
    @socketio.on("connect")
    def _on_connect():
        snap = pipeline.snapshot()
        socketio.emit("snapshot", snap.as_dict())

    # ---- REST endpoints ----------------------------------------------------
    @app.route("/")
    def index():
        return render_template("index.html",
                               device_profiles=config.DEVICE_PROFILES)

    @app.route("/api/state")
    def api_state():
        return jsonify(pipeline.snapshot().as_dict())

    @app.route("/api/alerts/<alert_id>/review", methods=["POST"])
    def api_review_alert(alert_id: str):
        ok = pipeline.mark_alert_reviewed(alert_id)
        return jsonify({"ok": ok})

    @app.route("/api/sim/rogue", methods=["POST"])
    def api_rogue():
        if not simulator:
            return jsonify({"ok": False, "error": "simulator not running"}), 400
        body = request.get_json(silent=True) or {}
        enabled = bool(body.get("enabled", True))
        if enabled:
            simulator.enable_rogue()
        else:
            simulator.disable_rogue()
        return jsonify({"ok": True, "enabled": simulator.rogue_active})

    @app.route("/api/sim/spoofer", methods=["POST"])
    def api_spoofer():
        if not simulator:
            return jsonify({"ok": False, "error": "simulator not running"}), 400
        body = request.get_json(silent=True) or {}
        enabled = bool(body.get("enabled", True))
        target = body.get("target", "sensor_node")
        if enabled:
            simulator.enable_spoofer(target=target)
        else:
            simulator.disable_spoofer()
        return jsonify({
            "ok": True,
            "enabled": simulator.spoofer_active,
            "target": target,
        })

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok", "system": pipeline.snapshot().system_status})

    return app, socketio
