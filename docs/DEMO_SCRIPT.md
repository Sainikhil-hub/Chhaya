# Chhaya — Demo Day Run of Show

*Innovation Day 2026 · Total: ~10 minutes + Q&A · Hardware: 1 × ESP8266 + 1 × phone*

---

## THE ONE LINE (memorize this)

> **"Chhaya (छाया) means shadow — every device leaves a shadow in its traffic
> pattern, even when the traffic is encrypted. We fingerprint that shadow with
> ML to identify devices and catch impostors — and we only ever read metadata,
> never content."**

---

## PART 0 — PREP (do tonight / 1 hour before)

### Flash the board back to SensorNode (do this TONIGHT)
The board is currently flashed with `04_spoofer`. For the opening you need:
1. Open `firmware/01_sensor_node/01_sensor_node.ino` → Upload.
2. Note the IP from Serial Monitor (should be 192.168.137.222 again).
3. **Rehearse the spoofer re-flash ONCE tonight**: open
   `firmware/04_spoofer/chhaya_config.h`, set `USE_STATIC_IP 1`,
   `DEVICE_IP "192.168.137.222"` (the IP the sensor had), gateway
   `192.168.137.1`. Compile it once so it's ready (IDE stays open, one click
   tomorrow). Then flash the sensor BACK for tonight.

### Checklist (30 min before)
- [ ] Windows hotspot "Chhaya" ON (Settings → Network → Mobile hotspot).
      Password: `demo12345`
- [ ] Laptop Wi-Fi: disable "connect automatically" on campus/other networks —
      if the laptop hops networks, the hotspot DIES.
- [ ] Firewall clean: `netsh advfirewall firewall show rule name="python.exe"`
      → must show nothing (if rules reappear, run docs/fix_firewall_python.ps1
      as admin).
- [ ] Start pipeline: `python scripts/run_demo.py --mode udp`
- [ ] Browser: http://localhost:5000 → Ctrl+Shift+R once.
- [ ] Verify: board card appears as SensorNode ~15 s after board powers on.
- [ ] Phone: UDP sender app, connected to hotspot Wi-Fi, both messages saved
      as drafts (see Act 4).
- [ ] Click "Mark reviewed" on any old alerts so the list starts clean.
- [ ] Board powered by laptop USB (cable doubles as "here is the real device"
      prop).

### Fallbacks (know these cold)
| Symptom | Fix (say "one moment" and do it) |
|---|---|
| Board card doesn't appear | Serial monitor: does it say "Connected"? Hotspot still ON? |
| Hotspot off | Settings → Mobile hotspot → On (board auto-reconnects) |
| Dashboard dead/frozen | Restart `run_demo.py --mode udp`, then Ctrl+Shift+R |
| Graph empty | Ctrl+Shift+R (page reload fixes it) |
| EVERYTHING hardware fails | `python scripts/run_demo.py` (software simulator) — same dashboard, the Demo Controls toggles WORK in that mode; demo rogue + spoofing with those buttons |

---

## PART 1 — THE HOOK (30 seconds)

Show the dashboard header. Say:

> "This is Chhaya — Hindi for *shadow*. You can't see a device's traffic
> contents anymore — everything is encrypted. But every device still leaves a
> shadow: the *sizes* of its packets and the *rhythm* of its timing leak
> through encryption. Chhaya fingerprints that shadow. Point at the logo:
> the crisp chip is the device; the blurred echo behind it is all we get to
> see — and it's enough."

---

## PART 2 — THE REAL DEVICE APPEARS (2 minutes)

Power on the ESP8266 (USB from laptop). While waiting (~15 s), narrate the
pipeline:

> "This board next to me is a real ESP8266 — a 300-rupee microcontroller. It's
> joining the hotspot on this laptop and sending UDP packets over the air.
> Watch the dashboard..."

The card appears: **SensorNode · ACTIVE**.

> "Chhaya has never seen this device before — no names, no MAC lookup. In
> about 15 seconds it measured the traffic and identified it as a sensor with
> this confidence."

Walk the 4 features on the card (each = one sentence):
- **avg size ~75 bytes** → "small payloads — sensor readings."
- **interval ~4-5 s** → "one reading every five seconds."
- **packets/min ~12-15** → "the steady rate."
- **burstiness ~0.01** → "almost zero jitter — sensors are metronomes, and
  that regularity IS the signature."

> "A camera would look completely different — kilobyte bursts 30 times a
> second. A smart switch — tiny irregular blips. Four numbers, a different
> shape per device type: that's the fingerprint. A machine-learning model
> trained on these profiles classifies every device live, every 2.5 seconds."

---

## PART 3 — THE HEARTBEAT (1 minute)

Point at the graph:

> "This is the network's heartbeat monitor. The green line is our sensor —
> flat and boring at ~15 packets a minute. That boredom is exactly the point:
> regularity is the signature. A camera would spike in bursts; a switch would
> stutter. And this is live — it's drawing right now."

---

## PART 4 — THE IMPOSTOR (3 minutes — THE SHOWSTOPPER)

**Pre-staged tonight:** Arduino IDE open with the spoofer sketch, config
already edited (`USE_STATIC_IP 1`, DEVICE_IP = the sensor's IP).

1. Click Upload. While it flashes (~30 s), talk — don't pause:

> "Now I'm re-flashing the SAME physical board to impersonate the sensor it
> just was — same IP, same claimed identity. This is exactly what malware
> does on a network: IP and MAC addresses are trivial to fake, and this
> attack needs no encryption-breaking at all. A firewall can't see it. An
> antivirus can't see it. The traffic is *allowed* — it's just lying about
> who it is."

2. Board reconnects → card shows **SensorNode** again, confidence high:

> "There it is — the classifier accepts it. A naive ML system is fooled.
> Because at any single moment, the impostor looks *close enough*."

3. Wait 15–30 s. **Red SPOOFING – CRITICAL alert fires**:

> "But Chhaya doesn't just ask *what does this device look like* — it asks
> *did this device change its story?* The spoofer sends slightly bigger
> packets, slightly faster — a z-score above 4 on the device's own baseline.
> The card flipped to SPOOFED. **The identity was stolen in one click; the
> behaviour couldn't be.** That is the thesis of Chhaya."

---

## PART 5 — THE PHONE (2 minutes, the bonus wow)

Phone: UDP sender app → IP `192.168.137.1`, Port `9999`.

**Beat 1 — rogue (amber):** message = the long ~600-byte text; tap SEND ~once
per second, 8–10 times.

> "Now a device Chhaya has NEVER seen — my own phone — joins the network.
> Within seconds: unknown device, flagged rogue."

**Beat 2 — disguise (green):** message = the exact 72-char text; tap SEND
once every ~4-5 s, steady, for a minute.

> "Same phone, now sending crafted packets — 72 bytes, five-second rhythm.
> It's classified as a SensorNode. My phone just impersonated a sensor.
> That's how malware hides — and why the behaviour-drift layer from the last
> demo matters: if it changes its story mid-act, it gets caught."

**Message texts:**
- Rogue (~600 B): `temp=24.5;hum=58;occ=3;` repeated 8× (about 600 chars)
- Sensor (exactly 72 chars): `temp=24.5;hum=58;occ=3;temp=24.5;hum=58;occ=3;temp=24.5;hum=58;occ=3;`

---

## PART 6 — REAL WORLD + PRIVACY CLOSE (1 minute)

> "The ESP8266 boards are just controlled stand-ins. In a real deployment
> Chhaya sits at the **router or gateway** and watches every device already on
> the network — TVs, cameras, plugs, watches — with zero setup per device.
> It still works when everything is encrypted, because it never reads
> contents — only sizes and timing. Privacy by design: we literally cannot
> read your messages; we only see their shadow. That's how a smart home or
> an enterprise finds the rogue device, the compromised fridge, the impostor —
> **even when the attacker has the keys and the encryption holds.**"

---

## LIKELY JUDGE QUESTIONS (and 15-second answers)

**"How is this different from a firewall/antivirus?"**
Firewalls and AV inspect contents or signatures. Chhaya uses *behavioural
metadata*, so it works on fully encrypted traffic and catches *allowed* traffic
that lies about its identity.

**"What if an attacker perfectly mimics the timing?"**
Then they've solved a hard control problem: matching mean, variance, and
burst structure across four features simultaneously, while the detector keeps
a rolling baseline. Any drift in any feature — z > 4 — fires. It raises the
cost from 'spoof an IP' (trivial) to 'statistically impersonate a device
perfectly, forever' (hard).

**"Phones randomize MAC addresses — doesn't that break it?"**
It's actually our best argument: the address can be faked, the behaviour
can't. That's exactly why you need behaviour-based identification.

**"What about NAT — many devices behind one IP?"**
Real limitation. On the LAN side (where Chhaya sits) devices are separable by
MAC/ARP; behind NAT you fingerprint the aggregate — still useful for anomaly
detection, honest to admit.

**"How accurate is the model?"**
Random Forest over the 4 features; in the profile space the classes are well
separated (sensor ~75 B/5 s vs camera ~1200 B/bursts vs switch ~32 B/irregular).
Low-confidence windows are labelled uncertain and can be flagged rogue —
demonstrated live.

**"Why ESP8266?"**
300 rupees, Wi-Fi built in, and it lets us generate *known, repeatable*
traffic profiles — the only honest way to validate a classifier end-to-end
with real radio traffic.

**"Privacy?"**
We never store or read payloads — the capture layer reads only size, time,
and source IP (by design, in code). Demonstrated: the phone's message content
is never shown anywhere.

---

## THE "HARDWARE OR SOFTWARE?" QUESTION (expect this — have it ready)

**Answer: Chhaya is software. The ESP8266 is a traffic generator, not part of
the system** — a test instrument that lets us validate the detector with known
ground truth, exactly like feeding a known signal into any detector in a lab.

**Real-world deployment (3 steps):**
1. Chhaya runs on a small always-on box at the network chokepoint — a
   Raspberry Pi next to the home router, on the router itself (OpenWRT), or a
   capture server on a managed switch's SPAN/mirror port in enterprises.
2. Devices don't connect to it — no agents, no setup. Their traffic already
   crosses the gateway; Chhaya passively observes. Works retroactively on an
   existing network.
3. Kernel capture (libpcap/Npcap) hands it packet HEADERS only: timestamp,
   length, source IP. Payload is never opened — and for HTTPS it's unreadable
   ciphertext anyway, while size/timing still leak. That's the shadow.

**Proof it's real in the code (show capture.py for 10 seconds):**
- `src/capture.py` → `make_source("udp" | "live" | "inprocess")` — three
  capture modes already built. `"live"` is scapy/Npcap sniffing with a
  configurable BPF filter (`config.py`: CAPTURE_BPF, CHHAYA_IFACE env).
- The packet handler reads `len(pkt)` + IP header — nothing else (REQ-4/6,
  metadata-only by construction).
- Deployment = same pipeline, one line changed: `make_source("live")`.

**"Isn't the traffic just replaying your config file?"**
Honest answer: the ESPs send the three profiles by design — controlled inputs
with ground truth to validate the pipeline. But the PHONE was a genuinely
unknown device: nothing in any config, never seen before, and Chhaya measured
and decided on its own. Real deployment retrains the same features on labeled
real devices (`scripts/train_model.py`); anything unrecognized is flagged
rogue — which is what caught the phone.

**"But in the demo devices connect to YOUR laptop — what about real networks?"**
In the demo the laptop is BOTH the router (Windows hotspot) and the analyzer,
so traffic comes to it. In deployment the analyzer moves to where traffic
already flows: on or behind the router (Raspberry Pi / OpenWRT at home,
SPAN/mirror port on enterprise switches). Every packet crosses the router
anyway — Chhaya reads headers there. Same capture code, different interface:
one config line (CAPTURE_INTERFACE / CAPTURE_BPF). This is the same vantage
point Wireshark, Zeek, and IDS tools have always used — we apply it to a new
question: device identity.

Encryption detail (airtight version): WPA2/3 protects the AIR and terminates
at the router — behind the AP, headers are already decrypted, so position
solves link encryption. HTTPS/VPN protects CONTENT end-to-end and stays
unreadable — but size and timing headers still travel in the clear, and
that's all we use. Link encryption solved by position; content encryption
solved by design.

Real-time: the pipeline classifies every 2.5 s continuously from rolling
12-second windows; per-device state is a small buffer, so a Pi-class box
handles a house or small office 24/7.

---

## GOLDEN RULES ON STAGE

1. Nothing is flashed live except the rehearsed spoofer one-click.
2. If anything hangs: "one moment" → checklist → keep talking.
3. Never touch the Demo Controls toggles in hardware mode (they're for the
   software fallback).
4. The alerts list is your trophy — let the red alert sit on screen while you
   deliver the punchline.
5. End on the tagline: *"Even encrypted, every device leaves a shadow —
   Chhaya reads the shadow."*
