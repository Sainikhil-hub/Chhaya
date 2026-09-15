/*
 * GhostPrint debug tool - Wi-Fi scanner
 * Lists every network the ESP8266 can see, with channel and signal.
 * Flash this, open Serial Monitor at 115200, and read the list.
 * Tells us if the board can see your hotspot at all.
 */

#include <ESP8266WiFi.h>

void setup() {
    Serial.begin(115200);
    delay(100);
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    delay(100);
    Serial.println("\n[scan] ready");
}

void loop() {
    Serial.println("[scan] scanning...");
    int n = WiFi.scanNetworks();
    Serial.printf("[scan] found %d networks:\n", n);
    for (int i = 0; i < n; i++) {
        Serial.printf("  %-32s ch%-2d %d dBm  %s\n",
                      WiFi.SSID(i).c_str(),
                      WiFi.channel(i),
                      WiFi.RSSI(i),
                      WiFi.encryptionType(i) == ENC_TYPE_NONE ? "open" : "secured");
    }
    Serial.println("[scan] ---------------------");
    delay(5000);
}
