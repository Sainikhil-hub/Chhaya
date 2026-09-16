# Chhaya — छाया

**IoT device identification via traffic fingerprinting.**

*Chhaya* (Hindi for **"shadow"**) identifies smart devices on a local network
purely from **how they communicate, not what they say**. Every device leaves a
shadow of itself in its traffic pattern — packet **sizes** and **timing**
rhythms leak through even when the traffic is fully encrypted. Chhaya
fingerprints that shadow, classifies the device with machine learning, and
catches devices that are **unknown** (rogue) or **pretending to be something
else** (spoofing) — reading **metadata only, never packet contents**.


<p align="center">
  <em>The crisp chip is the device — the blurred echo behind it is its shadow
  in the traffic. That shadow is all Chhaya needs.</em>
</p>

---

## How it works

| Stage | What happens |
|-------|--------------|
| **Generate** | ESP8266 boards (or a built-in Python simulator) emit realistic IoT traffic profiles: sensor node, camera stream, smart switch — plus a spoofer that mimics them with deliberate statistical drift. |
| **Capture** | Packet **metadata only** — timestamp, size, source IP. Payload bytes are never read (privacy by construction, see `src/capture.py`). |
| **Fingerprint** | Per-device rolling 12-second windows produce 4 features: avg packet size, inter-packet interval, packets/min, burstiness. |
| **Classify** | A Random Forest names the device and returns a confidence score; low-confidence windows are flagged *uncertain*. |
| **Detect** | A z-normalised distance-from-prototype check flags **rogue** devices; a per-device rolling baseline with a gated z-score flags **spoofing** (attack traffic never reshapes the baseline it is compared against). |
| **Display** | A Flask + SocketIO dashboard: live device cards, real-time packet-rate graph, colour-coded alert feed (amber = rogue, red = spoofing). |

## Why it matters

- Encryption protects **content**, not **behaviour** — this works even when
  every packet is HTTPS/VPN.
- IP and MAC identities are trivial to fake; statistical behaviour is not.
  Identity can be stolen in a click — the shadow can't.
- Zero per-device integration: in deployment, Chhaya observes passively from
  the network chokepoint (see [Real-world deployment](#real-world-deployment)).

## Quick start (no hardware required)

A built-in software simulator reproduces all three device profiles and both
attacks on a single laptop.

```bash
cd Chhaya
pip install -r requirements.txt
python scripts/run_demo.py          # auto-trains the model on first launch
# open http://localhost:5000
```

Three devices identify themselves within ~10 seconds. From the **Demo
Controls** panel:

- **Rogue Device ON** → amber alert: *"Unknown / rogue device detected"* within ~5 s
- **Spoofing Attack ON** (pick a target) → red critical alert within ~10 s:
  *"Possible spoofing: '127.0.0.11' is impersonating 'sensor_node' but feature
  ... has drifted"*

## With real ESP8266 hardware

The ESP8266 boards are **traffic generators** (test instruments), not part of
the analysis system — they let the pipeline be validated against known ground
truth over real Wi-Fi. The recommended flow needs **one board**:

1. Set your Wi-Fi + the laptop's IP in `firmware/chhaya_config.h` (a copy sits
   next to every sketch).
2. Flash `firmware/01_sensor_node/01_sensor_node.ino` → it appears on the
   dashboard as **SensorNode** within ~15 s.
3. For the spoofing act: set `USE_STATIC_IP 1` and the same IP in
   `firmware/04_spoofer/chhaya_config.h`, re-flash the **same board** — it
   keeps the victim's identity, sends drifted traffic, and the dashboard
   raises a **red spoofing alert**.
4. Bonus: a phone with any UDP-sender app targeting `<laptop-IP>:9999` appears
   as a device too — crafted sizes/rhythms can disguise it as a sensor; unknown
   patterns are flagged rogue.

Run the pipeline in UDP mode (no admin rights, no Npcap needed):

```bash
python scripts/run_demo.py --mode udp
```

Four boards (sensor / camera / switch / spoofer) can run simultaneously — each
joins the same network and gets its own device card. Full walkthrough:
**[docs/ONE_BOARD_TEST.md](docs/ONE_BOARD_TEST.md)**, including the Windows
firewall and hotspot gotchas.

Scapy/Npcap sniffing is also supported for passive capture on a monitored
interface:

```bash
python scripts/run_demo.py --mode live --interface "Wi-Fi"
```

## Real-world deployment

Chhaya is **software**; the hardware is a controlled signal source. In
deployment the same pipeline runs at the network chokepoint, where every
packet already passes:

- **Home / small office:** a Raspberry Pi-class box on or behind the router
  (or on the router itself, e.g. OpenWRT).
- **Enterprise:** a capture server on a managed switch's **SPAN/mirror port**.

Devices never connect *to* Chhaya — no agents, no per-device setup; their
traffic crosses the router anyway. WPA2/3 link encryption terminates at the
access point, so headers are readable there; end-to-end encryption (HTTPS/VPN)
stays unreadable — and only headers are ever used. Capture mode, training
data, and thresholds are all swappable in `config.py`; anything the model
doesn't recognise is flagged rogue rather than ignored.

## Project layout

```
Chhaya/
├── README.md
├── requirements.txt
├── config.py                     # all tunable parameters
├── firmware/                     # ESP8266/ESP32 Arduino sketches (dual-target)
│   ├── chhaya_config.h           # shared Wi-Fi config template
│   ├── 01_sensor_node/           # ~72 B every 5 s, metronome-steady
│   ├── 02_camera_stream/         # ~1200 B bursts (8-14 pkts) every 30 s
│   ├── 03_smart_switch/          # ~32 B, irregular events (+FLASH button)
│   ├── 04_spoofer/               # mimics a known profile with drift
│   └── 99_wifi_scan/             # radio diagnostic (Serial only)
├── src/
│   ├── capture.py                # inprocess / udp socket / scapy live capture
│   ├── features.py               # packet stream -> 4-feature vector
│   ├── classifier.py             # Random Forest train/predict
│   ├── detector.py               # rogue + spoofing detection
│   ├── traffic_simulator.py      # software IoT devices (laptop-only demo)
│   ├── pipeline.py               # orchestrator (windows, state, alerts)
│   └── utils.py                  # logging, JSON store, time helpers
├── dashboard/
│   ├── app.py                    # Flask + SocketIO backend
│   ├── templates/index.html      # dark SOC-style UI (shadow logo)
│   └── static/{css,js}/          # styles + live client logic
├── scripts/
│   ├── generate_training_data.py # build synthetic training CSV
│   ├── train_model.py            # train + save the RF model
│   ├── run_demo.py               # one-command launcher (--mode udp/live)
│   └── smoke_test.py             # end-to-end headless verification
├── docs/
│   ├── ONE_BOARD_TEST.md         # hardware walkthrough + troubleshooting
│   ├── DEMO_SCRIPT.md            # run-of-show for live demos
│   └── fix_firewall_python.ps1   # removes auto-created python.exe block rules
├── data/
│   ├── training/                 # training_data.csv
│   ├── models/                   # chhaya_rf.joblib
│   └── logs/                     # alerts.json, predictions.json (gitignored)
└── tests/                        # pytest suite (25 tests)
```

## Configuration

All knobs live in `config.py`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `WINDOW_SECONDS` | `12` | feature extraction window |
| `CLASSIFICATION_INTERVAL` | `2.5` | seconds between predictions |
| `CLASSIFIER_CONFIDENCE_THRESHOLD` | `0.55` | below this → *uncertain* |
| `SPOOFING_BASELINE_MIN_SAMPLES` | `6` | windows before judging spoofing |
| `SPOOFING_ZSCORE_THRESHOLD` | `4.0` | \|z\| above this on any feature → suspect |
| `SPOOFING_MIN_EXCEED_WINDOWS` | `2` | consecutive suspect windows → spoofing alert |
| `ROGUE_ZDISTANCE_THRESHOLD` | `30` | z-normalised distance from every class prototype → rogue |
| `DEVICE_PROFILES` | `{...}` | per-device packet size / interval / jitter |
| `CAPTURE_INTERFACE` | `None` | scapy interface for `--mode live` (`CHHAYA_IFACE` env) |
| `DASHBOARD_PORT` | `5000` | web UI port |

## Tests

```bash
python -m pytest tests/ -v          # 25 tests
python scripts/smoke_test.py        # headless end-to-end demo check (~75 s)
```

Covers feature extraction, classifier accuracy, rogue/spoofing detectors, and
the simulator (including the spoofer's identity takeover).

## Troubleshooting (Windows)

- **External packets never reach the dashboard, but loopback tests do?**
  A dismissed "Allow python.exe…" firewall popup silently creates `python.exe`
  **Block** rules, and Block beats any port Allow rule. Check with
  `netsh advfirewall firewall show rule name="python.exe"` and remove them with
  `docs/fix_firewall_python.ps1` (run as Administrator).
- **Mobile hotspot keeps turning itself off** when the laptop changes Wi-Fi
  networks — re-enable it; ESP boards auto-reconnect on their own.
- See `docs/ONE_BOARD_TEST.md` for the full session-tested checklist.

## Requirements trace (SRS)

| REQ | Where implemented |
|-----|-------------------|
| REQ-1/2/3 (distinct profiles, spoofer, auto-reconnect) | `firmware/*.ino`, `src/traffic_simulator.py` |
| REQ-4/5/6/7 (capture, 4 features, metadata-only, <2 s) | `src/capture.py`, `src/features.py` |
| REQ-8/9/10/11 (RF, label + confidence, ≥85 % accuracy, uncertain flag) | `src/classifier.py` |
| REQ-12/13/14 (rogue detection within 5 s, with source IP) | `src/detector.py:detect_rogue` |
| REQ-15/16/17 (per-device baseline, z-score spoofing, red alert) | `src/detector.py:update_and_detect_spoofing` |
| REQ-18/19/20/21/22 (dashboard, live graph, push alerts, colours, review) | `dashboard/app.py`, `dashboard/static/js/dashboard.js` |
| Reliability (NFR 5.3) — disconnect-tolerant devices | `src/pipeline.py` (idle status on no data) |
| Configurability (NFR 5.5) — thresholds in one config file | `config.py` |

## Tech stack

Python 3.10+ · scikit-learn (RandomForest) · Flask + Flask-SocketIO ·
Chart.js · scapy (optional live capture) · Arduino (ESP8266/ESP32 firmware)

## License

Research / educational use. RAIoT Lab, Amity University Rajasthan.
