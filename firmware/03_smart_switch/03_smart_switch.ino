/*
 * Chhaya - SmartSwitch firmware
 *
 * Simulates a smart switch that is mostly idle and only sends a tiny
 * packet when triggered. The "trigger" is simulated here as a random
 * event every ~1.8 seconds (with wide jitter), producing an irregular
 * pattern with high coefficient-of-variation (burstiness).
 *
 * Flash this to ESP8266 #3.
 *
 * Optionally wire a real button to GPIO0 (BOOT) so the operator can
 * trigger a packet on demand during the demo.
 */

#if defined(ESP32)
#include <WiFi.h>
#else
#include <ESP8266WiFi.h>
#endif
#include <WiFiUdp.h>
#include "chhaya_config.h"

#define DEVICE_LABEL "smart_switch"
#define AVG_PACKET_SIZE  32
#define SIZE_JITTER      6
#define AVG_INTERVAL_MS  1800
#define INTERVAL_JITTER  900
#define TRIGGER_GPIO     0   // FLASH/BOOT button on most ESP8266 dev boards

WiFiUDP udp;

int randInRange(int min, int max) {
    return min + (rand() % (max - min + 1));
}

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.printf("[%s] Booting...\n", DEVICE_LABEL);

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

void sendTinyPacket() {
    int sz = AVG_PACKET_SIZE + randInRange(-SIZE_JITTER, SIZE_JITTER);
    if (sz < 20) sz = 20;
    uint8_t buf[64];
    memset(buf, 0x5A, sizeof(buf));
    udp.beginPacket(TARGET_IP, TARGET_PORT);
    udp.write(buf, sz);
    udp.endPacket();
}

void loop() {
    if (WiFi.status() != WL_CONNECTED) {
        WiFi.reconnect();
        delay(2000);
        return;
    }

    // Manual trigger
    if (digitalRead(TRIGGER_GPIO) == LOW) {
        sendTinyPacket();
        delay(200); // debounce
    }

    // Random event trigger
    int gap = AVG_INTERVAL_MS + randInRange(-INTERVAL_JITTER, INTERVAL_JITTER);
    if (gap < 200) gap = 200;
    delay(gap);
    sendTinyPacket();
}
