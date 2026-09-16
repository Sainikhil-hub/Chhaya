# One-ESP8266 Hardware Test Guide

You need: **1 × ESP8266, 1 × USB cable, your laptop, your phone hotspot** ("realme 6 Pro").
The ESP8266 sends real UDP packets over Wi-Fi; Chhaya receives and identifies it —
no Npcap, no admin rights, no extra hardware.

> Why the phone hotspot: campus Wi-Fi (Amity-wifi) blocks device-to-device traffic
> and needs a web portal login, which the ESP8266 cannot do. A hotspot gives you a
> clean private network.

---

## Step 0 — Connect everything to the hotspot (5 min)

1. Phone: turn on the **realme 6 Pro** hotspot.
2. Laptop: connect to the hotspot.
3. Find the laptop's IP on the hotspot:
   ```
   ipconfig
   ```
   Under "Wireless LAN adapter Wi-Fi" note the **IPv4 Address** (e.g. `10.148.242.229`).
4. Open `firmware/chhaya_config.h` and check the three values:
   ```c
   #define WIFI_SSID     "realme 6 Pro"
   #define WIFI_PASSWORD "7674029485"
   #define TARGET_IP     "10.148.242.229"   // <- must equal the laptop IP you just noted
   #define TARGET_PORT   9999
   ```
   If your laptop got a different IP, update `TARGET_IP` — everything else stays.

## Step 1 — Allow the packets through Windows Firewall (one time, admin)

PowerShell **as Administrator**:
```powershell
New-NetFirewallRule -DisplayName "Chhaya UDP 9999" -Direction Inbound -Protocol UDP -LocalPort 9999 -Action Allow
```
(If you skip this, the packets arrive but Windows silently drops them.)

## Step 2 — Flash the board (Arduino IDE)

1. Connect the ESP8266 via USB.
2. Open `firmware/01_sensor_node/01_sensor_node.ino` (the config file sits next to it).
3. Tools → Board: **NodeMCU 1.0 (ESP-12E Module)** (or *Generic ESP8266 Module*); needs the
   "esp8266" Arduino board package (Boards Manager → search "esp8266").
   Tools → Port: the COM port that appears.
4. Upload. If it prints `Connecting... ____` without writing: **hold the FLASH button**
   (the ESP8266 name for BOOT), click Upload, release when it says `Writing...`.
5. Open Serial Monitor at **115200** — you should see:
   ```
   [sensor_node] Connected, IP=10.148.242.xxx
   ```
   Note that IP — you'll need it for the spoofing test later.

> ESP8266 notes: the sketches are dual-target (`#if defined(ESP32)` … `#else ESP8266WiFi`),
> so the same code runs on both. In the spoofer, the runtime target-cycle button on GPIO0
> is the **FLASH** button on a NodeMCU board.

## Step 3 — Run Chhaya in hardware mode

```bash
cd D:\innovation\Chhaya
python scripts/run_demo.py --mode udp
```
Open **http://localhost:5000**. Within ~10–15 seconds a new device card appears
(the board's IP) identified as **SensorNode**, confidence climbing toward 1.00,
with its live packet-rate trace on the graph. That is the real end-to-end demo:
radio → packets → fingerprint → ML → dashboard.

**If nothing appears after ~30 s:** check Serial Monitor shows "Connected",
check `TARGET_IP` matches `ipconfig`, and check the firewall rule (Step 1).

## Step 4 — Spoofing attack with the SAME board (the showstopper)

The re-flashed board impersonates the device it just was:

1. In `firmware/chhaya_config.h` set (use the IP you noted in Step 2):
   ```c
   #define USE_STATIC_IP 1
   #define DEVICE_IP     "10.148.242.xxx"   // the IP the board had as SensorNode
   #define WIFI_GATEWAY  "10.148.242.1"     // usually the laptop IP ending .1 — check `ipconfig` "Default Gateway"
   ```
2. Open and upload `firmware/04_spoofer/04_spoofer.ino` to the same board.
3. Keep Chhaya running. The board now transmits **as the SensorNode's IP**
   with subtly wrong timing (10% bigger packets, 15% faster rhythm).
4. Within **~10–15 s** the dashboard fires a **red critical alert**:
   `Possible spoofing: '10.148.242.xxx' is impersonating 'sensor_node' ...`

   You can change the impersonated device at runtime with the **FLASH button**
   on the ESP8266 (cycles sensor → camera → switch).

## Step 5 — Rogue device (bonus, one more re-flash)

Upload `firmware/02_camera_stream/02_camera_stream.ino` — it appears as a NEW IP
(DHCP), gets identified as CameraStream. To see the amber rogue alert instead,
the traffic must be unknown: easiest is the dashboard's built-in **Rogue Device**
toggle (software twin), which fires in ≤ 5 s without any re-flashing.

---

## Quick reference

| What | Where |
|------|-------|
| Wi-Fi / laptop IP config | `firmware/chhaya_config.h` (edit `TARGET_IP` after `ipconfig`) |
| Sensor firmware (start here) | `firmware/01_sensor_node/01_sensor_node.ino` |
| Spoofer firmware | `firmware/04_spoofer/04_spoofer.ino` |
| Run hardware mode | `python scripts/run_demo.py --mode udp` |
| Run software mode (fallback) | `python scripts/run_demo.py` |
| Dashboard | http://localhost:5000 |

**Demo-day fallback plan:** if the hotspot misbehaves, run the full software demo
(`python scripts/run_demo.py`) — identical story, zero hardware, already verified.
