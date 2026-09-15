"""Software IoT device simulator.

Generates traffic patterns matching the three defined device profiles
(SensorNode, CameraStream, SmartSwitch) plus a Rogue device and a
Spoofer. The simulator emits real UDP packets on the local network so
the same capture pipeline that reads ESP8266 traffic also reads these.

For environments where raw sockets are restricted (or to keep the
demo fully self-contained), the simulator can also feed packets
directly into the pipeline via ``SimulatorSource.feed_to``. This is the
default mode because it requires no admin / Npcap / extra NICs.
"""
from __future__ import annotations

import random
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable

import config
from src.utils import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Packet dataclass
# ---------------------------------------------------------------------------
@dataclass
class SimPacket:
    src_ip: str
    dst_ip: str
    size: int
    timestamp: float
    protocol: str = "UDP"


# ---------------------------------------------------------------------------
# Device simulators
# ---------------------------------------------------------------------------
class _BaseDevice(threading.Thread):
    """Shared threading + lifecycle for a simulated device."""

    def __init__(self, name: str, src_ip: str, profile_key: str,
                 on_packet: Callable[[SimPacket], None] | None = None):
        super().__init__(daemon=True, name=f"sim-{name}")
        self.name = name
        self.src_ip = src_ip
        self.profile_key = profile_key
        self.profile = config.DEVICE_PROFILES[profile_key]
        self.on_packet = on_packet
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._pause.set()  # not paused initially
        self.rng = random.Random(hash(name) & 0xFFFF_FFFF)

    def stop(self) -> None:
        self._stop.set()
        self._pause.set()

    def pause(self) -> None:
        self._pause.clear()

    def resume(self) -> None:
        self._pause.set()

    def run(self) -> None:
        try:
            self._run()
        except Exception:
            log.exception("Simulator %s crashed", self.name)

    def _emit(self, size: int, ts: float | None = None) -> None:
        pkt = SimPacket(
            src_ip=self.src_ip,
            dst_ip=config.SIMULATOR_TARGET_IP,
            size=size,
            timestamp=ts if ts is not None else time.time(),
        )
        if self.on_packet:
            try:
                self.on_packet(pkt)
            except Exception:
                log.exception("on_packet callback failed for %s", self.name)

    def _sleep(self, timeout: float) -> bool:
        """Sleep for `timeout` seconds in small slices so stop / pause
        are responsive. Returns False if a stop was requested."""
        if timeout <= 0:
            return not self._stop.is_set()
        end = time.time() + timeout
        while time.time() < end:
            if self._stop.is_set():
                return False
            # If we're paused, wait until resumed or stopped
            if not self._pause.is_set():
                self._pause.wait(timeout=0.05)
                continue
            time.sleep(min(0.05, end - time.time()))
        return not self._stop.is_set()


class SensorNodeSimulator(_BaseDevice):
    """Steady small packets every ~5 seconds (slight jitter)."""

    def __init__(self, on_packet=None):
        super().__init__("sensor_node", config.SIMULATOR_SOURCE_IPS["sensor_node"],
                         "sensor_node", on_packet)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._pause.wait()  # blocks while paused
            if self._stop.is_set():
                return
            size = max(20, int(self.rng.gauss(self.profile["avg_packet_size"],
                                              self.profile["packet_size_jitter"])))
            self._emit(size)
            interval = max(0.05, self.rng.gauss(
                self.profile["inter_packet_interval_ms"] / 1000.0,
                self.profile["interval_jitter_ms"] / 1000.0))
            self._sleep(interval)


class CameraStreamSimulator(_BaseDevice):
    """Large bursts every ~30 seconds (8-14 packets per burst)."""

    def __init__(self, on_packet=None):
        super().__init__("camera_stream", config.SIMULATOR_SOURCE_IPS["camera_stream"],
                         "camera_stream", on_packet)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._pause.wait()
            if self._stop.is_set():
                return
            burst_low, burst_high = self.profile["burst_packet_count"]
            n_packets = self.rng.randint(burst_low, burst_high)
            for _ in range(n_packets):
                size = max(60, int(self.rng.gauss(self.profile["avg_packet_size"],
                                                   self.profile["packet_size_jitter"])))
                self._emit(size)
                inner_interval = max(0.005, self.rng.gauss(
                    self.profile["inter_packet_interval_ms"] / 1000.0,
                    self.profile["interval_jitter_ms"] / 1000.0))
                if self._sleep(inner_interval) is False:
                    return
            # Sleep between bursts
            burst_interval = max(0.5, self.rng.gauss(
                self.profile["burst_interval_ms"] / 1000.0,
                self.profile["burst_interval_ms"] / 1000.0 * 0.1))
            self._sleep(burst_interval)


class SmartSwitchSimulator(_BaseDevice):
    """Tiny packets only when triggered (event-driven)."""

    def __init__(self, on_packet=None):
        super().__init__("smart_switch", config.SIMULATOR_SOURCE_IPS["smart_switch"],
                         "smart_switch", on_packet)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._pause.wait()
            if self._stop.is_set():
                return
            # Idle gap â€“ event-driven device.
            idle = max(0.1, self.rng.gauss(
                self.profile["inter_packet_interval_ms"] / 1000.0,
                self.profile["interval_jitter_ms"] / 1000.0))
            if self._sleep(idle) is False:
                return
            size = max(20, int(self.rng.gauss(self.profile["avg_packet_size"],
                                              self.profile["packet_size_jitter"])))
            self._emit(size)


class RogueDeviceSimulator(_BaseDevice):
    """Unknown device. Emits traffic clearly outside every known profile."""

    def __init__(self, on_packet=None):
        super().__init__("rogue", config.SIMULATOR_SOURCE_IPS["rogue"],
                         "rogue", on_packet)
        self.rng = random.Random(0xBADF00D)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._pause.wait()
            if self._stop.is_set():
                return
            size = self.rng.randint(400, 900)
            self._emit(size)
            interval = self.rng.uniform(0.3, 1.2)
            self._sleep(interval)


class SpooferSimulator(_BaseDevice):
    """Mimics another device's profile but with subtle statistical drift.

    The spoofer emits packets with the TARGET device's source IP: it is
    impersonating that device's identity on the network, so the pipeline
    attributes its traffic to the victim and the victim's z-score baseline
    is what catches the drift.
    """

    # Drift calibration: strong enough that per-window z-scores exceed
    # SPOOFING_ZSCORE_THRESHOLD within ~1-2 windows, yet subtle enough that
    # the classifier still labels the traffic confidently as the target
    # (uncertain windows would take the rogue path instead of spoofing).
    SIZE_DRIFT = 1.10
    SIZE_JITTER_SCALE = 2.0
    INTERVAL_DRIFT = 0.85
    INTERVAL_JITTER_SCALE = 2.0

    def __init__(self, on_packet=None, target_profile: str = "sensor_node"):
        super().__init__("spoofer", config.SIMULATOR_SOURCE_IPS["spoofer"],
                         target_profile, on_packet)
        self.target_profile = target_profile
        self.rng = random.Random(0xDEFACED)
        self.set_target(target_profile)

    def set_target(self, target_profile: str) -> None:
        self.target_profile = target_profile
        self.profile_key = target_profile
        self.profile = config.DEVICE_PROFILES[target_profile]
        # Assume the victim's identity (source IP).
        self.src_ip = config.SIMULATOR_SOURCE_IPS[target_profile]

    def _run(self) -> None:
        while not self._stop.is_set():
            self._pause.wait()
            if self._stop.is_set():
                return
            prof = config.DEVICE_PROFILES[self.target_profile]
            # Match the target's profile but inject subtle drift on the
            # mean and jitter so the defender can spot the impersonation.
            size = max(20, int(self.rng.gauss(
                prof["avg_packet_size"] * self.SIZE_DRIFT,
                prof["packet_size_jitter"] * self.SIZE_JITTER_SCALE)))
            self._emit(size)
            interval = max(0.05, self.rng.gauss(
                prof["inter_packet_interval_ms"] / 1000.0 * self.INTERVAL_DRIFT,
                prof["interval_jitter_ms"] / 1000.0 * self.INTERVAL_JITTER_SCALE))
            self._sleep(interval)


# ---------------------------------------------------------------------------
# Optional: real network emission (used when ESP8266 boards are not present
# but the operator still wants to see real packets on the wire).
# ---------------------------------------------------------------------------
class WireEmitter:
    """Send raw UDP packets via the system socket stack.

    Note: real wire emission requires the receiver to be on the same
    network. The simulator's default mode is in-process via on_packet
    callbacks, which is simpler and portable.
    """

    def __init__(self, target_ip: str = None, target_port: int = None):
        self.target_ip = target_ip or config.SIMULATOR_TARGET_IP
        self.target_port = target_port or config.SIMULATOR_TARGET_PORT
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, payload: bytes) -> None:
        self._sock.sendto(payload, (self.target_ip, self.target_port))

    def close(self) -> None:
        self._sock.close()


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------
class SimulatorOrchestrator:
    """Starts / stops / configures all simulation threads."""

    def __init__(self, on_packet: Callable[[SimPacket], None]):
        self._on_packet = on_packet
        self.sensor = SensorNodeSimulator(on_packet)
        self.camera = CameraStreamSimulator(on_packet)
        self.switch = SmartSwitchSimulator(on_packet)
        self.rogue = RogueDeviceSimulator(on_packet)
        self.spoofer = SpooferSimulator(on_packet, target_profile="sensor_node")
        self.rogue_active = False
        self.spoofer_active = False
        self._spoofed_device: _BaseDevice | None = None

    def _real_device(self, target: str) -> _BaseDevice | None:
        return {"sensor_node": self.sensor,
                "camera_stream": self.camera,
                "smart_switch": self.switch}.get(target)

    def start(self) -> None:
        self.sensor.start()
        self.camera.start()
        self.switch.start()
        # NOTE: spoofer and rogue are NOT started here. They are toggled
        # on/off from the demo controls so the operator can demonstrate
        # attack -> detection scenarios on demand.
        log.info("Simulator started (sensor / camera / switch)")

    def stop(self) -> None:
        for sim in (self.sensor, self.camera, self.switch, self.rogue, self.spoofer):
            sim.stop()
        log.info("Simulator stopped")

    def enable_rogue(self) -> None:
        if self.rogue_active:
            return
        self.rogue = RogueDeviceSimulator(self._on_packet)
        self.rogue.start()
        self.rogue_active = True
        log.info("Rogue device enabled")

    def disable_rogue(self) -> None:
        if not self.rogue_active:
            return
        self.rogue.stop()
        self.rogue_active = False
        log.info("Rogue device disabled")

    def enable_spoofer(self, target: str = "sensor_node") -> None:
        if target not in config.KNOWN_DEVICE_LABELS:
            target = "sensor_node"
        # Release the previous victim, if we were mid-attack.
        if self._spoofed_device is not None:
            self._spoofed_device.resume()
            self._spoofed_device = None
        if self.spoofer.is_alive():
            self.spoofer.stop()
        # Identity takeover: the clone emits as the victim's IP while the
        # real device is silenced, exactly as an impersonation attack does.
        victim = self._real_device(target)
        if victim is not None:
            victim.pause()
            self._spoofed_device = victim
        self.spoofer = SpooferSimulator(self._on_packet, target_profile=target)
        self.spoofer.start()
        self.spoofer_active = True
        log.info("Spoofer enabled (target=%s, assuming its identity)", target)

    def disable_spoofer(self) -> None:
        self.spoofer.stop()
        self.spoofer_active = False
        if self._spoofed_device is not None:
            self._spoofed_device.resume()
            self._spoofed_device = None
        log.info("Spoofer disabled")

