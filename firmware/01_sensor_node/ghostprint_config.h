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

// Device label is overridden by each sketch.
