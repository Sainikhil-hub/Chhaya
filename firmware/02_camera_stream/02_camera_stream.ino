/*
 * Chhaya - CameraStream firmware
 *
 * Simulates a security camera that streams a large burst of data
 * every ~30 seconds. Each burst contains 8-14 large UDP packets
 * spaced ~33 ms apart. This produces a high-mean / high-burstiness
 * fingerprint that is easy for the Random Forest to distinguish
 * from the other two profiles.
 *
 * Flash this to ESP8266 #2.
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include "chhaya_config.h"

#define DEVICE_LABEL "camera_stream"
#define AVG_PACKET_SIZE  1200
#define SIZE_JITTER      180
#define INNER_INTERVAL_MS 33      // intra-burst gap
#define INNER_JITTER_MS    8
#define BURST_PACKETS_MIN  8
#define BURST_PACKETS_MAX 14
#define BURST_INTERVAL_MS  30000  // gap between bursts

WiFiUDP udp;

int randInRange(int min, int max) {
    return min + (rand() % (max - min + 1));
}

void connectWifi() {
    WiFi.mode(WIFI_STA);
#if USE_STATIC_IP
    // Pin the board's identity (one-board spoofing demo - see config).
    IPAddress staticIp;  staticIp.fromString(DEVICE_IP);
    IPAddress gateway;   gateway.fromString(WIFI_GATEWAY);
    WiFi.config(staticIp, gateway, IPAddress(255, 255, 255, 0));
    Serial.printf("Using static IP %s
", DEVICE_IP);
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
}

void sendBurst() {
    int n = randInRange(BURST_PACKETS_MIN, BURST_PACKETS_MAX);
    for (int i = 0; i < n; i++) {
        int sz = AVG_PACKET_SIZE + randInRange(-SIZE_JITTER, SIZE_JITTER);
        if (sz < 60) sz = 60;
        uint8_t buf[1500];
        memset(buf, (i & 0xFF), sizeof(buf));
        udp.beginPacket(TARGET_IP, TARGET_PORT);
        udp.write(buf, sz);
        udp.endPacket();
        int inner = INNER_INTERVAL_MS + randInRange(-INNER_JITTER_MS, INNER_JITTER_MS);
        if (inner < 5) inner = 5;
        delay(inner);
    }
}

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.printf("[%s] Booting...\n", DEVICE_LABEL);
    connectWifi();
    udp.begin(0);
    randomSeed(analogRead(0) ^ micros());
}

void loop() {
    if (WiFi.status() != WL_CONNECTED) {
        WiFi.reconnect();
        delay(2000);
        return;
    }
    sendBurst();
    int gap = BURST_INTERVAL_MS + randInRange(-3000, 3000);
    if (gap < 500) gap = 500;
    delay(gap);
}
