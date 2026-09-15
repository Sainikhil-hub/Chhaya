"""Tests for the traffic simulator (REQ-1/2)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from src.traffic_simulator import (  # noqa: E402
    CameraStreamSimulator,
    SensorNodeSimulator,
    SimPacket,
    SmartSwitchSimulator,
    SpooferSimulator,
    RogueDeviceSimulator,
)


def _collect(sim, duration_sec: float = 1.5) -> list[SimPacket]:
    captured: list[SimPacket] = []
    sim.on_packet = lambda pkt: captured.append(pkt)
    sim.start()
    time.sleep(duration_sec)
    sim.stop()
    sim.join(timeout=2.0)
    return captured


def test_sensor_node_emits_packets():
    sim = SensorNodeSimulator()
    pkts = _collect(sim, duration_sec=2.0)
    assert len(pkts) > 0
    assert all(p.src_ip == config.SIMULATOR_SOURCE_IPS["sensor_node"] for p in pkts)
    assert all(p.size > 0 for p in pkts)


def test_camera_stream_emits_bursts():
    sim = CameraStreamSimulator()
    pkts = _collect(sim, duration_sec=2.0)
    assert len(pkts) > 0
    # Camera packets should be the largest profile
    assert all(p.size > 100 for p in pkts)


def test_smart_switch_emits_small_packets():
    sim = SmartSwitchSimulator()
    pkts = _collect(sim, duration_sec=6.0)  # switch sleeps ~1.8s (+-0.9) before its first packet
    assert len(pkts) > 0
    assert all(p.size < 100 for p in pkts)


def test_rogue_device_emits():
    sim = RogueDeviceSimulator()
    pkts = _collect(sim, duration_sec=1.5)
    assert len(pkts) > 0
    assert all(p.src_ip == config.SIMULATOR_SOURCE_IPS["rogue"] for p in pkts)


def test_spoofer_can_change_target():
    sim = SpooferSimulator(target_profile="sensor_node")
    captured = []
    sim.on_packet = lambda pkt: captured.append(pkt)
    sim.start()
    time.sleep(1.0)
    sim.set_target("camera_stream")
    sizes_phase1 = [p.size for p in captured]
    time.sleep(1.0)
    sim.stop()
    sim.join(timeout=2.0)
    # The spoofer should continue emitting after the target change
    assert len(captured) > 0
    assert all(p.size > 0 for p in captured)


def test_spoofer_assumes_target_identity():
    """The spoofer must emit with the victim's source IP (identity takeover)."""
    sim = SpooferSimulator(target_profile="camera_stream")
    captured = []
    sim.on_packet = lambda pkt: captured.append(pkt)
    sim.start()
    time.sleep(1.5)
    sim.stop()
    sim.join(timeout=2.0)
    assert len(captured) > 0
    victim_ip = config.SIMULATOR_SOURCE_IPS["camera_stream"]
    assert all(p.src_ip == victim_ip for p in captured)


def test_orchestrator_enable_spoofer_starts_emission():
    """Regression: enable_spoofer() must actually start the spoofer thread
    (it previously only resumed an event, so no packets were ever emitted)."""
    from src.traffic_simulator import SimulatorOrchestrator

    captured: list[SimPacket] = []
    orch = SimulatorOrchestrator(on_packet=captured.append)
    orch.start()
    victim_ip = config.SIMULATOR_SOURCE_IPS["sensor_node"]

    # Let the real sensor emit a couple of packets, then take it over.
    time.sleep(1.0)
    before = sum(1 for p in captured if p.src_ip == victim_ip)

    orch.enable_spoofer(target="sensor_node")
    assert orch.spoofer_active
    time.sleep(2.5)
    orch.disable_spoofer()
    assert not orch.spoofer_active

    after = sum(1 for p in captured if p.src_ip == victim_ip)
    # Spoofer emits immediately as the victim, so the victim's packet count
    # must keep growing even though the real sensor is silenced.
    assert after > before
    # After disabling, the real sensor resumes within its normal interval.
    time.sleep(5.5)
    resumed = sum(1 for p in captured if p.src_ip == victim_ip)
    assert resumed > after
    orch.stop()
