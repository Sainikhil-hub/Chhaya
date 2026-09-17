/*
 * Chhaya - Spoofer firmware
 *
 * A 4th ESP8266 that mimics one of the three known devices on command.
 * The packet size and interval are roughly matched to the target
 * profile but with subtle statistical drift (larger jitter, slight
 * offset on the mean) so the spoofing detector can spot the
 * impersonation.
 *
 * Flash this to ESP8266 #4. Choose the target profile by setting
 * SPOOF_TARGET below, or use the FLASH (BOOT) button (GPIO0) to cycle
 * through targets at runtime.
 *
 * SPOOF_TARGET one of:
 *   "sensor_node"
 *   "camera_stream"
 *   "smart_switch"
 */

#if defined(ESP32)
#include <WiFi.h>
#else
#include <ESP8266WiFi.h>
#endif
#include <WiFiUdp.h>
#include "chhaya_config.h"

#define DEVICE_LABEL "spoofer"
#define TRIGGER_GPIO 0

#ifndef SPOOF_TARGET
#define SPOOF_TARGET "sensor_node"
#endif

WiFiUDP udp;

struct Profile {
    const char *name;
    int avg_size;
    int size_jitter;
    int avg_interval_ms;
    int interval_jitter;
};

const Profile PROFILES[] = {
    { "sensor_node",   72,   12,    5000,  400 },
    { "camera_stream", 1200, 180,   33,    8 },
    { "smart_switch",  32,   6,     1800,  900 },
};

int current_target = 0;

static void initTarget() {
    for (int i = 0; i < 3; i++) {
        if (strcmp(SPOOF_TARGET, PROFILES[i].name) == 0) {
            current_target = i;
            break;
        }
    }
}

int randInRange(int min, int max) {
    return min + (rand() % (max - min + 1));
}

int driftSize(int base, int jitter) {
    // Calibrated to match the software spoofer (SpooferSimulator):
    // subtle enough that the classifier stays confident, visible enough
    // that the z-score baseline flags it within seconds.
    int sz = (int)(base * 1.10f) + randInRange(-(int)(jitter * 2.0f), (int)(jitter * 2.0f));
    if (sz < 20) sz = 20;
    return sz;
}

int driftInterval(int base, int jitter) {
    int v = (int)(base * 0.85f) + randInRange(-(int)(jitter * 2.0f), (int)(jitter * 2.0f));
    if (v < 50) v = 50;
    return v;
}

void sendPacket(const Profile &p) {
    int sz = driftSize(p.avg_size, p.size_jitter);
    uint8_t buf[1500];
    memset(buf, 0xC3, sizeof(buf));
    udp.beginPacket(TARGET_IP, TARGET_PORT);
    udp.write(buf, sz);
    udp.endPacket();
}

void cycleTarget() {
    current_target = (current_target + 1) % 3;
    Serial.printf("[%s] Now mimicking %s\n", DEVICE_LABEL,
                  PROFILES[current_target].name);
}

void setup() {
    initTarget();
    Serial.begin(115200);
    delay(200);
    Serial.printf("[%s] Booting - mimicking %s\n", DEVICE_LABEL,
                  PROFILES[current_target].name);

    pinMode(TRIGGER_GPIO, INPUT_PULLUP);

    WiFi.mode(WIFI_STA);
#if USE_STATIC_IP
    // Pin the board's identity (one-board spoofing demo - see config).
    IPAddress staticIp;  staticIp.fromString(DEVICE_IP);
    IPAddress gateway;   gateway.fromString(WIFI_GATEWAY);
    WiFi.config(staticIp, gateway, IPAddress(255, 255, 255, 0));
        Serial.printf("Using static IP %s\n", DEVICE_IP);
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
    }
    udp.begin(0);
    randomSeed(analogRead(0) ^ micros());
}

void loop() {
    if (WiFi.status() != WL_CONNECTED) {
        WiFi.reconnect();
        delay(2000);
        return;
    }

    if (digitalRead(TRIGGER_GPIO) == LOW) {
        cycleTarget();
        delay(400);
    }

    const Profile &p = PROFILES[current_target];
    sendPacket(p);
    int delay_ms = driftInterval(p.avg_interval_ms, p.interval_jitter);
    delay(delay_ms);
}
