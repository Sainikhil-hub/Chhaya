// =================================================================
// Chhaya - Common Wi-Fi configuration
// Edit this file with your network credentials and then #include it
// from each firmware sketch. Keep it in the same folder as the .ino.
// =================================================================

#pragma once

// Set these to your local Wi-Fi network. All ESP8266 boards and the
// capture laptop must join the same network.
#ifndef WIFI_SSID
#define WIFI_SSID "Chhaya"
#endif

#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "demo12345"
#endif

// IP address of the capture laptop (the PC running Wireshark + the
// Chhaya pipeline). Packets are sent to this address on the
// TARGET_PORT below.
#ifndef TARGET_IP
#define TARGET_IP "192.168.137.1"
#endif

#ifndef TARGET_PORT
#define TARGET_PORT 9999
#endif

// ---- Fixed device identity (ONE-BOARD spoofing demo) ----
// 1 = the board pins its IP, so a re-flash keeps the victim's identity.
// DEVICE_IP must equal the IP the sensor board currently holds, and
// WIFI_GATEWAY is the Windows hotspot router (192.168.137.1).
#ifndef USE_STATIC_IP
#define USE_STATIC_IP 1
#endif
#ifndef DEVICE_IP
#define DEVICE_IP "192.168.137.100"
#endif
#ifndef WIFI_GATEWAY
#define WIFI_GATEWAY "192.168.137.1"
#endif

// Device label is overridden by each sketch.
