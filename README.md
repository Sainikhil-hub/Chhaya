# Chhaya

**IoT device identification via network traffic fingerprinting.**

Chhaya identifies smart devices on a local network purely from how they
communicate, not what they say. It learns the behavioural fingerprint of each
device (packet size, inter-packet interval, packet rate, burstiness), then uses
machine learning to identify the device in real time, alert on unknown /
rogue devices, and detect traffic spoofing.

> RAIoT Lab - Innovation Day submission (2026)
> IEEE SRS-aligned (22 functional requirements across 6 system features)

---

## What it does

| Stage | What happens |
|-------|--------------|
| **Simulate** | Three ESP8266 boards (or a Python simulator) emit distinct, realistic IoT traffic patterns: sensor node, camera stream, smart switch. |
| **Capture**  | Wireshark / scapy reads packet **metadata only** (size, timing, source IP) - never the payload. |
| **Fingerprint** | Per-device rolling windows produce 4 features: avg packet size, inter-packet interval, packets/min, burstiness (coefficient of variation). |
| **Classify** | A Random Forest classifier names the active device and returns a confidence score. |
| **Detect** | A scale-aware distance-from-prototype check flags rogue / unknown devices; a gated per-device z-score baseline (attack traffic never reshapes the baseline) flags spoofing attempts. |
| **Display** | A Flask + Socket.IO dashboard shows live device cards, a 60-second traffic graph, and a colour-coded alert feed (amber = rogue, red = spoofing). |

## Why it matters

- Encrypted traffic still leaks device identity through behavioural patterns.
- This is a real, documented IoT security & privacy concern.
- The system demonstrates *attack vs defender* using a 4th ESP8266 that mimics a known device.

## Quick start (no ESP8266 required)

The project ships with a software simulator so the entire demo runs on a
single laptop.

```bash
# 1. Clone / extract the project
cd Chhaya

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the demo (auto-trains a model on first launch)
python scripts/run_demo.py

# 4. Open the dashboard
#    http://localhost:5000
```

You should see three devices identified (SensorNode, CameraStream, SmartSwitch)
with live confidence scores. Use the demo controls on the dashboard to:

- Toggle **Rogue Device** -> an amber alert appears when the unknown device
  connects.
- Toggle **Spoofing Attack** -> a red alert appears within ~10 seconds when the
  spoofer ESP8266 (or its software twin) starts mimicking a known device.

## With real ESP8266 boards

When you have the hardware:

1. Edit `firmware/chhaya_config.h` and set your Wi-Fi SSID/password and
   the capture laptop's IP.
2. Open each `.ino` sketch in Arduino IDE, select your ESP8266 board, and
   upload:
   - `firmware/01_sensor_node/01_sensor_node.ino` -> ESP8266 #1
   - `firmware/02_camera_stream/02_camera_stream.ino` -> ESP8266 #2
   - `firmware/03_smart_switch/03_smart_switch.ino` -> ESP8266 #3
   - `firmware/04_spoofer/04_spoofer.ino` -> ESP8266 #4
3. Connect all four ESP8266 boards and the capture laptop to the same Wi-Fi.
4. Run the demo in live mode:

```bash
python scripts/run_demo.py --mode live --interface "Wi-Fi"
```

(Interface name varies by OS - on Windows check `ipconfig`; on Linux use
`ip link show`.)

The firmware sketches use only the Arduino `WiFi.h` + `WiFiUdp.h` libraries -
no extra packages needed.

## Project layout

```
Chhaya/
├── README.md
├── requirements.txt
├── config.py                     # all tunable parameters
├── firmware/                     # ESP8266 Arduino sketches
│   ├── chhaya_config.h
│   ├── 01_sensor_node/
│   ├── 02_camera_stream/
│   ├── 03_smart_switch/
│   └── 04_spoofer/
├── src/
│   ├── features.py               # packet -> feature vector
│   ├── classifier.py             # Random Forest train/predict
│   ├── detector.py               # rogue + spoofing detection
│   ├── capture.py                # InProcess + scapy live capture
│   ├── traffic_simulator.py      # software IoT devices
│   ├── pipeline.py               # orchestrator
│   └── utils.py                  # logging, JSON store, time helpers
├── dashboard/
│   ├── app.py                    # Flask + SocketIO backend
│   ├── templates/index.html      # dark security-tool UI
│   └── static/{css,js}/          # styles + live client logic
├── scripts/
│   ├── generate_training_data.py # build synthetic training CSV
│   ├── train_model.py            # train + save the RF model
│   ├── run_demo.py               # one-command launcher
│   └── smoke_test.py             # end-to-end verification
├── data/
│   ├── training/                 # training_data.csv
│   ├── models/                   # chhaya_rf.joblib
│   └── logs/                     # alerts.json, predictions.json
└── tests/                        # pytest suite (21 tests)
```

## Configuration

All knobs live in `config.py`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `WINDOW_SECONDS` | `12` | feature extraction window (REQ-5) |
| `CLASSIFICATION_INTERVAL` | `2.5` | seconds between predictions (REQ-18) |
| `CLASSIFIER_CONFIDENCE_THRESHOLD` | `0.55` | below this -> uncertain (REQ-11) |
| `SPOOFING_BASELINE_MIN_SAMPLES` | `8` | windows before judging spoofing (REQ-15/16) |
| `SPOOFING_ZSCORE_THRESHOLD` | `4.0` | \|z\| above this on any feature -> suspect |
| `SPOOFING_MIN_EXCEED_WINDOWS` | `2` | consecutive suspect windows -> spoofing alert |
| `ROGUE_ZDISTANCE_THRESHOLD` | `30` | z-normalised distance from every class prototype -> rogue |
| `DEVICE_PROFILES` | `{}` | per-device packet-size / interval / jitter |
| `SIMULATOR_SOURCE_IPS` | `{}` | virtual loopback IPs for the simulator |
| `CAPTURE_INTERFACE` | `None` | scapy interface for `--mode live` |
| `DASHBOARD_PORT` | `5000` | web UI port |

## Tests

```bash
python -m pytest tests/ -v
```

25 tests covering feature extraction, classifier accuracy, the rogue /
spoofing detectors, and the simulator (including the spoofer's identity
takeover behaviour).

## Pre-showcase health check

```bash
python scripts/smoke_test.py
```

Runs the full demo flow headlessly (~75 s) and exits non-zero if any step
fails: device identification, rogue alerting, and spoofing alerting.

## Demo flow (judge walkthrough)

1. **Boot** - Run `python scripts/run_demo.py`. Browser opens to a dark
   SOC-style dashboard showing three identified devices within ~10 seconds.
2. **Live traffic** - Point out the live graph showing packet-rate
   differences (camera spikes, sensor is steady, switch is sporadic).
3. **Rogue** - Click *Rogue Device* ON. Within ~5s an amber alert appears:
   "Unknown / rogue device detected on the network".
4. **Spoofing** - Select *SensorNode* in the spoofer dropdown, click ON.
   The spoofer assumes the SensorNode's identity on the network; within
   ~5-10s a red critical alert appears: "Possible spoofing: '127.0.0.11'
   is impersonating 'sensor_node' but feature ... has drifted".
5. **Mark reviewed** - Click "Mark reviewed" on any alert; it goes grey.

## Requirements trace (SRS)

| REQ | Where implemented |
|-----|-------------------|
| REQ-1/2/3 (ESP8266 distinct profiles, spoofer, auto-reconnect) | `firmware/*.ino`, `src/traffic_simulator.py` |
| REQ-4/5/6/7 (capture, 4 features, metadata-only, <2s) | `src/capture.py`, `src/features.py` |
| REQ-8/9/10/11 (RF, label+confidence, ≥85% accuracy, uncertain flag) | `src/classifier.py` |
| REQ-12/13/14 (rogue detection within 5s, with source IP) | `src/detector.py:detect_rogue` |
| REQ-15/16/17 (per-device baseline, z-score spoofing, red alert) | `src/detector.py:update_and_detect_spoofing` |
| REQ-18/19/20/21/22 (dashboard updates, live graph, push alerts, colour, mark reviewed) | `dashboard/app.py`, `dashboard/templates/index.html`, `dashboard/static/js/dashboard.js` |
| Reliability (NFR 5.3) - ESP8266 disconnect tolerant | `src/pipeline.py:_on_packet`, idle status on no data |
| Configurability (NFR 5.5) - thresholds in config file | `config.py` |

## Tech stack

- Python 3.10+
- scikit-learn (RandomForestClassifier)
- Flask + Flask-SocketIO (live updates)
- Chart.js (live traffic graph)
- scapy (live capture, optional)
- Arduino + ESP8266 (firmware)

## License

Research / educational use. RAIoT Lab, Amity University Rajasthan.