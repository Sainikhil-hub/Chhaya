/*
 * GhostPrint - SensorNode firmware
 *
 * Simulates an environmental sensor node:
 *   - Sends a small UDP packet every ~5 seconds (with small jitter)
 *   - Packet size ~72 bytes (occupancy / temperature simulation)
 *
 * Flash this to ESP8266 #1. Configure Wi-Fi in ghostprint_config.h.
 * The packet contents are dummy; only metadata is used by GhostPrint.
 */

#if defined(ESP32)
#include <WiFi.h>
#else
#include <ESP8266WiFi.h>
#endif
#include <WiFiUdp.h>
#include "ghostprint_config.h"

#define DEVICE_LABEL "sensor_node"
#define AVG_PACKET_SIZE  72
#define SIZE_JITTER      12
#define AVG_INTERVAL_MS  5000
#define INTERVAL_JITTER  400

WiFiUDP udp;
unsigned long lastSend = 0;

// Random helpers
int randInRange(int min, int max) {
    return min + (rand() % (max - min + 1));
}

int nextPacketSize() {
    int sz = AVG_PACKET_SIZE + randInRange(-SIZE_JITTER, SIZE_JITTER);
    return (sz < 20) ? 20 : sz;
}

unsigned long nextIntervalMs() {
    long v = AVG_INTERVAL_MS + randInRange(-INTERVAL_JITTER, INTERVAL_JITTER);
    return (v < 200) ? 200 : (unsigned long)v;
}

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.printf("[%s] Booting...\n", DEVICE_LABEL);

    WiFi.mode(WIFI_STA);
#if USE_STATIC_IP
    // Pin the board's identity (one-board spoofing demo - see config).
    IPAddress staticIp;  staticIp.fromString(DEVICE_IP);
    IPAddress gateway;   gateway.fromString(WIFI_GATEWAY);
    WiFi.config(staticIp, gateway, IPAddress(255, 255, 255, 0));
    Serial.printf("[%s] Using static IP %s\n", DEVICE_LABEL, DEVICE_IP);
#endif
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 60) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[%s] Connected, IP=%s\n", DEVICE_LABEL,
                      WiFi.localIP().toString().c_str());
    } else {
        Serial.printf("\n[%s] Wi-Fi failed - will keep retrying.\n", DEVICE_LABEL);
    }
    udp.begin(0);
    randomSeed(analogRead(0) ^ micros());
}

void loop() {
    // REQ-3: auto-reconnect on Wi-Fi drop.
    if (WiFi.status() != WL_CONNECTED) {
        WiFi.reconnect();
        delay(2000);
        return;
    }

    unsigned long now = millis();
    if (now - lastSend >= nextIntervalMs()) {
        lastSend = now;
        int sz = nextPacketSize();
        uint8_t buf[256];
        memset(buf, 0xA5, sizeof(buf));
        // Only send the bytes we want to claim - payload is ignored by
        // GhostPrint but the on-wire size becomes the "packet size"
        // feature.
        udp.beginPacket(TARGET_IP, TARGET_PORT);
        udp.write(buf, sz);
        udp.endPacket();
    }
    delay(10);
}