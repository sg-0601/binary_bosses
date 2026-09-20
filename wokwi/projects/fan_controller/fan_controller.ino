/**
 * Industrial Cooling Fan Controller Firmware (ESP32 Arduino Target)
 * Problem Statement 3 Wokwi Simulation Firmware
 */

#include <Arduino.h>

#define TEMP_THRESHOLD_CELSIUS 30.0f
#define FAN_PIN 13
#define STATUS_LED_PIN 12

typedef enum {
    SYSTEM_INIT = 0,
    SYSTEM_NORMAL_COOLING,
    SYSTEM_FAN_ACTIVE,
    SYSTEM_SENSOR_FAULT
} SystemState_t;

static SystemState_t current_state = SYSTEM_INIT;
static bool fan_relay_state = false;

void set_fan(bool enable) {
    fan_relay_state = enable;
    digitalWrite(FAN_PIN, enable ? HIGH : LOW);
    Serial.printf("[GPIO] Fan Relay Pin %d set to %s\n", FAN_PIN, enable ? "HIGH (ON)" : "LOW (OFF)");
}

void process_temperature(float temp) {
    if (temp < -20.0f || temp > 120.0f) {
        current_state = SYSTEM_SENSOR_FAULT;
        set_fan(false);
        Serial.printf("[ALERT] ERROR: SENSOR_DISCONNECTED or invalid reading (%.1f C)!\n", temp);
        Serial.printf("[STATE] Transitioned to SYSTEM_SENSOR_FAULT\n");
        return;
    }

    if (temp > TEMP_THRESHOLD_CELSIUS) {
        current_state = SYSTEM_FAN_ACTIVE;
        set_fan(true);
        Serial.printf("[INFO] Temp: %.1f C -> Threshold Exceeded (>%.1f C). Fan: ON\n", temp, TEMP_THRESHOLD_CELSIUS);
    } else {
        current_state = SYSTEM_NORMAL_COOLING;
        set_fan(false);
        Serial.printf("[INFO] Temp: %.1f C -> Normal Range (<=%.1f C). Fan: OFF\n", temp, TEMP_THRESHOLD_CELSIUS);
    }
}

void setup() {
    Serial.begin(115200);
    delay(200);
    pinMode(FAN_PIN, OUTPUT);
    digitalWrite(FAN_PIN, LOW);
    Serial.println("[SYSTEM_BOOT] Industrial Firmware v1.0.0 initializing...");
    Serial.printf("[CONFIG] Temp Threshold: %.1f C, Fan GPIO: %d\n", TEMP_THRESHOLD_CELSIUS, FAN_PIN);

    process_temperature(25.0f);
    delay(100);
    process_temperature(32.5f);
    delay(100);
    process_temperature(28.0f);
    delay(100);
    process_temperature(-99.0f);
    delay(100);
    Serial.println("[SYSTEM_SHUTDOWN] Test execution completed.");
}

void loop() {
    delay(1000);
}
