// =================================================================
// GhostPrint - Common Wi-Fi configuration
// Edit this file with your network credentials and then #include it
// from each firmware sketch. Keep it in the same folder as the .ino.
// =================================================================

#pragma once

// Set these to your local Wi-Fi network. All ESP8266 boards and the
// capture laptop must join the same network.
#ifndef WIFI_SSID
#define WIFI_SSID "realme 6 Pro"
#endif

#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "7674029485"
#endif

// IP address of the capture laptop (the PC running Wireshark + the
// GhostPrint pipeline). Packets are sent to this address on the
// TARGET_PORT below.
#ifndef TARGET_IP
#define TARGET_IP "10.148.242.229"
#endif

#ifndef TARGET_PORT
#define TARGET_PORT 9999
#endif

// ---- Fixed device identity (for the ONE-BOARD spoofing demo) ----
// Set USE_STATIC_IP to 1 to pin this board's IP address. Phase A
// (identification): leave 0, note the IP the board gets (Serial
// Monitor or dashboard). Phase B (spoofing): set 1 and put that same
// IP in DEVICE_IP, then flash 04_spoofer - the re-flashed board keeps
// the victim's identity, exactly like a real impersonation attack.
#ifndef USE_STATIC_IP
#define USE_STATIC_IP 0
#endif
#ifndef DEVICE_IP
#define DEVICE_IP "192.168.4.50"
#endif
#ifndef WIFI_GATEWAY
#define WIFI_GATEWAY "192.168.4.1"
#endif

// Device label is overridden by each sketch.
