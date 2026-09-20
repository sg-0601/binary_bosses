#include <Arduino.h>

#define TEMP_THRESHOLD 30.0f
#define FAN_PIN 13
#define DHT_PIN 4

float simulated_temperature = 32.5f;

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("FIRMWARE_TEST_STARTED");
    pinMode(FAN_PIN, OUTPUT);

    // Simulated temperature reading
    Serial.print("TEMPERATURE: ");
    Serial.print(simulated_temperature);
    Serial.println(" C");

    // Simple fan-control condition
    if (simulated_temperature > TEMP_THRESHOLD) {
        digitalWrite(FAN_PIN, HIGH);
        Serial.println("FAN_ON");
    } else {
        digitalWrite(FAN_PIN, LOW);
        Serial.println("FAN_OFF");
    }

    Serial.println("FIRMWARE_TEST_SUCCESS");
}

void loop() {
    delay(1000);
}
