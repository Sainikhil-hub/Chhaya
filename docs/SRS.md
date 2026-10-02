# Chhaya Software Requirements Specification

## 1 Introduction

### 1.1 Purpose

This document specifies the implemented requirements for Chhaya, an IoT device-identification and security-monitoring prototype. Chhaya identifies traffic sources from behavioural metadata rather than packet payload content. It supports controlled simulator and hardware demonstrations, detects unknown traffic, and detects behavioural spoofing.

### 1.2 Scope

Chhaya processes timestamp, packet-size, source-IP, destination-IP, and protocol metadata. It derives a rolling traffic fingerprint and classifies it as one of three reference profiles: SensorNode, CameraStream, or SmartSwitch. It provides rogue-device and spoofing alerts through a local web dashboard.

The project supports these operating modes:

- In-process simulator for a hardware-free demonstration.
- Direct UDP reception from ESP8266/ESP32 boards or other UDP senders.
- Combined simulator and UDP listener mode for a phone plus software demonstration.
- Optional passive Scapy capture on a monitored network interface.

### 1.3 Definitions

| Term | Definition |
| --- | --- |
| Traffic fingerprint | A set of behavioural features derived from packet metadata. |
| Rogue device | A traffic source whose feature vector does not match the known profiles. |
| Spoofing | A known-looking traffic source whose current behaviour drifts from its trusted baseline. |
| Burstiness | A measure of variation or clustering in packet timing. |
| Combined mode | A source that accepts both in-process simulated packets and real UDP datagrams. |

## 2 Product Description

### 2.1 Product Perspective

Chhaya is a local network-security prototype. It is not a replacement for a firewall or full intrusion-detection suite. Its contribution is behavioural device identification: it evaluates communication rhythm and packet size even when application content is encrypted.

### 2.2 Users

| User | Main Activities |
| --- | --- |
| Operator | Starts the pipeline, selects a capture mode, monitors the dashboard, and reviews alerts. |
| Evaluator or judge | Views device classifications, traffic graphs, and security-alert outcomes. |
| Demonstrator | Uses simulator controls, a phone UDP sender, or an ESP8266/ESP32 traffic generator to show test scenarios. |

### 2.3 Operating Environment

- Python 3.10 or later on Windows, Linux, or macOS.
- Local browser access to the Flask dashboard on port 5000.
- Local UDP listener on port 9999 for direct and combined modes.
- A shared Wi-Fi network or hotspot for phones and hardware senders.
- Optional Npcap plus Scapy for passive live capture on Windows.

## 3 Architecture Requirements

### 3.1 Capture Sources

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-1 | The system shall accept in-process simulator packets through `InProcessSource`. | High |
| REQ-2 | The system shall receive direct UDP datagrams on configurable port 9999 through `UdpSource`. | High |
| REQ-3 | The system shall provide a combined source that accepts simulator packets and real UDP datagrams concurrently. | High |
| REQ-4 | The system shall optionally capture IP traffic with Scapy through `LiveCaptureSource`. | Medium |
| REQ-5 | All capture sources shall emit the same metadata-only packet representation to the pipeline. | High |

### 3.2 Packet Privacy

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-6 | The pipeline shall use timestamp, size, source IP, destination IP, and protocol metadata for analysis. | High |
| REQ-7 | The application shall not parse, store, or display UDP payload content for fingerprinting. | High |

### 3.3 Feature Extraction

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-8 | The pipeline shall group packets independently by source IP address. | High |
| REQ-9 | The pipeline shall derive average packet size, inter-packet interval, packets per minute, and burstiness. | High |
| REQ-10 | The default analysis window shall be 12 seconds. | High |
| REQ-11 | The default classification interval shall be 2.5 seconds. | High |

## 4 Functional Requirements

### 4.1 Traffic Generation

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-12 | The simulator shall generate SensorNode, CameraStream, and SmartSwitch traffic profiles. | High |
| REQ-13 | The simulator shall be able to generate an unknown rogue profile. | High |
| REQ-14 | The simulator shall be able to generate a spoofing profile against a selected known target. | High |
| REQ-15 | Firmware traffic generators shall support ESP8266 and ESP32-compatible boards. | Medium |

### 4.2 Classification

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-16 | The system shall use a Random Forest classifier for known device-profile prediction. | High |
| REQ-17 | The classifier shall return a label and confidence score for each processed feature vector. | High |
| REQ-18 | The system shall represent predictions below the configured confidence threshold as uncertain. | High |
| REQ-19 | The supported known labels shall include SensorNode, CameraStream, and SmartSwitch. | High |

### 4.3 Rogue Detection

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-20 | The system shall compare incoming feature vectors with known class prototypes. | High |
| REQ-21 | The system shall mark a source rogue when it is uncertain or sufficiently distant from every known profile. | High |
| REQ-22 | A rogue alert shall include the source IP, timestamp, severity, and explanatory message. | High |
| REQ-23 | Rogue alerts shall be displayed as amber in the dashboard. | High |

### 4.4 Spoofing Detection

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-24 | The system shall maintain a rolling baseline for each established known source. | High |
| REQ-25 | The baseline shall retain recent feature windows and expire after a configured absence interval. | High |
| REQ-26 | The detector shall compare current known-device traffic against its baseline with a z-score method. | High |
| REQ-27 | The detector shall require configured consecutive exceedances before raising a spoofing alert. | High |
| REQ-28 | Suspicious attack traffic shall not update the trusted baseline used for comparison. | High |
| REQ-29 | Spoofing alerts shall be displayed as red critical alerts in the dashboard. | High |

### 4.5 Dashboard

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-30 | The dashboard shall show known and observed source IPs with active, idle, rogue, or spoofed state. | High |
| REQ-31 | The dashboard shall show the latest four fingerprint features and classification result for each source. | High |
| REQ-32 | The dashboard shall show a rolling packet-rate graph. | High |
| REQ-33 | The dashboard shall receive device and alert updates without a manual page refresh. | High |
| REQ-34 | The operator shall be able to mark displayed alerts as reviewed. | Medium |
| REQ-35 | When the simulator is running, the dashboard shall allow rogue and spoofing scenarios to be toggled. | High |

### 4.6 Phone Demonstration

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-36 | The command `python scripts/run_demo.py --phone` shall start the simulator and UDP listener together. | High |
| REQ-37 | A phone or other UDP sender on the same local network shall be accepted as an additional source. | High |
| REQ-38 | Phone traffic shall undergo the same feature extraction, classification, and alert path as simulated traffic. | High |
| REQ-39 | A phone with an unknown traffic pattern shall normally be eligible for rogue detection. | High |

## 5 Non Functional Requirements

| Area | Requirement |
| --- | --- |
| Performance | The pipeline should produce classifications at the configured interval while retaining per-source rolling windows. |
| Reliability | A silent source shall become idle without stopping processing for other sources. |
| Privacy | The system shall analyse metadata only and shall not expose message payloads in the dashboard or logs. |
| Usability | The local dashboard shall make current device state and alert severity understandable through labels and colour. |
| Maintainability | Thresholds, profiles, paths, ports, and timing values shall be configurable from `config.py`. |
| Testability | The project shall include unit tests and an end-to-end smoke-test script for simulator scenarios. |
| Deployment | The same pipeline shall support a local demo, a router-adjacent device, or a monitored mirror-port environment by selecting the appropriate source. |

## 6 Interfaces

### 6.1 Commands

```powershell
python scripts/run_demo.py
python scripts/run_demo.py --phone
python scripts/run_demo.py --mode udp
python scripts/run_demo.py --mode live --interface "Wi-Fi"
```

### 6.2 Network Interfaces

- Dashboard HTTP endpoint: `http://localhost:5000`
- UDP receiver: `0.0.0.0:9999`
- Passive live-capture filter: UDP traffic destined for port 9999 by default

### 6.3 Hardware Interfaces

- ESP8266/ESP32 boards may act as controlled UDP traffic generators.
- A phone UDP sender may act as a real external traffic source in combined mode.
- Hardware is optional for the simulator-only workflow.

## 7 Constraints and Limitations

- The supplied model is trained on controlled traffic profiles, not a broad commercial-device dataset.
- Device separation depends on a visible source identity at the capture point; NAT can aggregate multiple devices behind one source address.
- Passive capture on Windows requires suitable interface access and Npcap.
- The prototype is intended for research and demonstration; it is not a full production IDS.
- Network observation must be authorised and comply with applicable privacy and security policies.

## 8 Acceptance Criteria

The updated project is acceptable when:

1. The simulator identifies the three reference profiles on the dashboard.
2. The rogue control produces an amber alert.
3. The spoofing control produces a red alert after baseline conditions are met.
4. Direct UDP mode accepts traffic from a configured ESP8266/ESP32 board.
5. Combined mode accepts a phone UDP sender while simulated devices remain active.
6. The dashboard displays device features, current status, packet-rate history, and reviewable alerts.

