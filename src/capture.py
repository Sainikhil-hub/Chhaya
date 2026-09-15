"""Packet capture layer.

Two capture sources are supported:

* ``InProcessSource`` – the simulator feeds packets directly into the
  pipeline via callbacks. This is the default for the laptop demo and
  requires no admin / Npcap / Wireshark.
* ``LiveCaptureSource`` – uses scapy to sniff real UDP/TCP packets on a
  chosen interface. This is used when ESP8266 boards are physically
  attached to the network.

Both sources yield the same ``CapturedPacket`` dataclass so the rest of
the pipeline is identical.

REQ-4/6: we read only metadata (size, timestamp, source IP) and never
the packet payload.
"""
from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator

import config
from src.utils import get_logger

log = get_logger(__name__)


@dataclass
class CapturedPacket:
    src_ip: str
    dst_ip: str
    size: int
    timestamp: float
    protocol: str = "UDP"


# ---------------------------------------------------------------------------
# In-process source (simulator-friendly)
# ---------------------------------------------------------------------------
class InProcessSource:
    """A queue-based source that the simulator writes to."""

    def __init__(self):
        self._handlers: list[Callable[[CapturedPacket], None]] = []
        self._lock = threading.Lock()
        self._running = False

    def add_handler(self, handler: Callable[[CapturedPacket], None]) -> None:
        with self._lock:
            self._handlers.append(handler)

    def feed(self, pkt) -> None:
        """Submit a packet (from simulator or any in-process producer)."""
        # Accept either a CapturedPacket or a SimPacket (same shape).
        cp = CapturedPacket(
            src_ip=pkt.src_ip,
            dst_ip=pkt.dst_ip,
            size=pkt.size,
            timestamp=pkt.timestamp,
            protocol=getattr(pkt, "protocol", "UDP"),
        )
        with self._lock:
            handlers = list(self._handlers)
        for h in handlers:
            try:
                h(cp)
            except Exception:
                log.exception("handler raised in InProcessSource")

    def start(self) -> None:
        self._running = True
        log.info("InProcessSource started")

    def stop(self) -> None:
        self._running = False
        log.info("InProcessSource stopped")


# ---------------------------------------------------------------------------
# Live capture (scapy)
# ---------------------------------------------------------------------------
class LiveCaptureSource:
    """Sniff UDP/TCP packets on a chosen interface.

    Uses scapy's ``AsyncSniffer`` so the call is non-blocking. Filters
    capture to metadata only - packet payload is never read or stored.
    """

    def __init__(self, interface: str | None = None,
                 bpf_filter: str | None = None):
        self.interface = interface or config.CAPTURE_INTERFACE
        self.bpf_filter = bpf_filter or config.CAPTURE_BPF
        self._handlers: list[Callable[[CapturedPacket], None]] = []
        self._lock = threading.Lock()
        self._sniffer = None

    def add_handler(self, handler: Callable[[CapturedPacket], None]) -> None:
        with self._lock:
            self._handlers.append(handler)

    def start(self) -> None:
        try:
            from scapy.all import AsyncSniffer, IP, UDP, TCP  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "scapy is required for live capture. "
                "pip install scapy (and install Npcap on Windows)."
            ) from e

        from scapy.all import AsyncSniffer

        def _on_pkt(pkt):
            if not pkt.haslayer("IP"):
                return
            ip_layer = pkt["IP"]
            size = len(pkt)  # total frame length - metadata only
            proto = "UDP" if pkt.haslayer("UDP") else ("TCP" if pkt.haslayer("TCP") else "OTHER")
            cp = CapturedPacket(
                src_ip=ip_layer.src,
                dst_ip=ip_layer.dst,
                size=size,
                timestamp=time.time(),
                protocol=proto,
            )
            with self._lock:
                handlers = list(self._handlers)
            for h in handlers:
                try:
                    h(cp)
                except Exception:
                    log.exception("scapy handler raised")

        self._sniffer = AsyncSniffer(
            iface=self.interface,
            filter=self.bpf_filter,
            prn=_on_pkt,
            store=False,
        )
        self._sniffer.start()
        log.info("LiveCaptureSource sniffing on iface=%s filter=%s",
                 self.interface, self.bpf_filter)

    def stop(self) -> None:
        if self._sniffer is not None:
            self._sniffer.stop()
            self._sniffer = None
        log.info("LiveCaptureSource stopped")


# ---------------------------------------------------------------------------
# UDP socket source (ESP8266-friendly, no Npcap needed)
# ---------------------------------------------------------------------------
class UdpSource:
    """Receive UDP datagrams sent directly by ESP8266 boards.

    Binds a plain UDP socket on the capture laptop; each datagram from a
    board becomes one CapturedPacket. Needs no admin rights and no Npcap,
    unlike scapy sniffing - this is the recommended mode for the
    single-board hardware demo. Payload bytes are never read (REQ-6):
    only the sender IP and datagram length are used.
    """

    def __init__(self, host: str = "0.0.0.0", port: int | None = None):
        self.host = host
        self.port = port or config.CAPTURE_LISTEN_PORT
        self._handlers: list[Callable[[CapturedPacket], None]] = []
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None
        self._stop = threading.Event()

    def add_handler(self, handler: Callable[[CapturedPacket], None]) -> None:
        with self._lock:
            self._handlers.append(handler)

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.settimeout(0.5)
        self._stop.clear()
        threading.Thread(target=self._loop, daemon=True,
                         name="ghostprint-udp-source").start()
        log.info("UdpSource listening on %s:%d", self.host, self.port)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            cp = CapturedPacket(
                src_ip=addr[0],
                dst_ip=self._sock.getsockname()[0],
                size=len(data),
                timestamp=time.time(),
                protocol="UDP",
            )
            with self._lock:
                handlers = list(self._handlers)
            for h in handlers:
                try:
                    h(cp)
                except Exception:
                    log.exception("udp handler raised")

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        log.info("UdpSource stopped")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def make_source(mode: str = "inprocess", interface: str | None = None):
    """Return a configured capture source.

    Parameters
    ----------
    mode : "inprocess" | "live" | "udp"
    interface : str, optional
        Used only when mode == "live".
    """
    if mode == "live":
        return LiveCaptureSource(interface=interface)
    if mode == "udp":
        return UdpSource()
    return InProcessSource()
