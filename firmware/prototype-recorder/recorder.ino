// Caseback phase 1 recorder for the Seeed XIAO nRF52840.
//
// Reads the MAX30101 (green, red, IR), the BMI270 (accelerometer and gyroscope) and the NTC divider,
// and prints one CSV row per PPG sample over USB serial. Not built or run on hardware yet: see README.md.
//
// Wiring (3.3 V logic):
//   MAX30101  VIN->3V3, GND->GND, SDA->D4, SCL->D5
//   BMI270    VCC->3V3, GND->GND, SDA->D4, SCL->D5, CS->3V3 (selects I2C), SDO->GND (address 0x68)
//   NTC       3V3 -> NTC -> D0 -> 10 kOhm -> GND
//
// Libraries: "SparkFun MAX3010x Pulse and Proximity Sensor Library" and "SparkFun BMI270 Arduino Library".
// Board: "Seeed XIAO nRF52840" from the "Seeed nRF52 Boards" package.

#include <Wire.h>
#include "MAX30105.h"
#include "SparkFun_BMI270_Arduino_Library.h"

// PPG settings. Output rate = SAMPLE_RATE / SAMPLE_AVERAGE = 100 Hz.
// LED_POWER is 0.2 mA per step: 0x3F is about 12.6 mA. Raise it if the green channel is too weak on the wrist.
static const byte LED_POWER = 0x3F;
static const byte SAMPLE_AVERAGE = 4;
static const byte LED_MODE = 3;        // red + IR + green
static const int SAMPLE_RATE = 400;
static const int PULSE_WIDTH = 411;
static const int ADC_RANGE = 16384;
static const float NOMINAL_FS = SAMPLE_RATE / (float)SAMPLE_AVERAGE;

static const uint8_t NTC_PIN = A0;

MAX30105 ppg;
BMI270 imu;
uint32_t sampleIndex = 0;

void halt(const char *msg) {
  while (true) {
    Serial.print("# ERROR ");
    Serial.println(msg);
    delay(1000);
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 4000) {}

  Wire.begin();
  Wire.setClock(400000);

  if (!ppg.begin(Wire, I2C_SPEED_FAST)) halt("MAX30101 not found on I2C 0x57");
  ppg.setup(LED_POWER, SAMPLE_AVERAGE, LED_MODE, SAMPLE_RATE, PULSE_WIDTH, ADC_RANGE);

  if (imu.beginI2C(BMI2_I2C_PRIM_ADDR) != BMI2_OK) halt("BMI270 not found on I2C 0x68");

  analogReadResolution(12);

  Serial.println("# caseback-recorder v1");
  Serial.print("# nominal_fs_hz=");
  Serial.println(NOMINAL_FS);
  Serial.println("n,ms,green,red,ir,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,ntc_adc12");
}

void loop() {
  ppg.check();
  while (ppg.available()) {
    uint32_t red = ppg.getFIFORed();
    uint32_t ir = ppg.getFIFOIR();
    uint32_t green = ppg.getFIFOGreen();
    ppg.nextSample();

    imu.getSensorData();

    Serial.print(sampleIndex++);
    Serial.print(',');
    Serial.print(millis());
    Serial.print(',');
    Serial.print(green);
    Serial.print(',');
    Serial.print(red);
    Serial.print(',');
    Serial.print(ir);
    Serial.print(',');
    Serial.print(imu.data.accelX, 4);
    Serial.print(',');
    Serial.print(imu.data.accelY, 4);
    Serial.print(',');
    Serial.print(imu.data.accelZ, 4);
    Serial.print(',');
    Serial.print(imu.data.gyroX, 2);
    Serial.print(',');
    Serial.print(imu.data.gyroY, 2);
    Serial.print(',');
    Serial.print(imu.data.gyroZ, 2);
    Serial.print(',');
    Serial.println(analogRead(NTC_PIN));
  }
}
