#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>

// Most 16x2 I2C LCD backpacks use address 0x27.
// If the LCD stays blank, try 0x3F or run the included I2C scanner.
LiquidCrystal_I2C lcd(0x27, 16, 2);

// DHT11 three-pin module wiring:
// S (signal) -> Arduino D2
// middle/VCC -> Arduino 5V
// -/GND -> Arduino GND
const uint8_t DHT_PIN = 2;
#define DHT_TYPE DHT11
DHT dht(DHT_PIN, DHT_TYPE);

const char STUDENT_NAME[] = "HITAYEZU Frank Duff";

const uint8_t LCD_COLUMNS = 16;
const uint8_t NAME_GAP = 3;

// DHT11 is a slow sensor, so read it once every two seconds.
const unsigned long TEMPERATURE_INTERVAL_MS = 2000;
const unsigned long SCROLL_INTERVAL_MS = 350;

unsigned long lastTemperatureTime = 0;
unsigned long lastScrollTime = 0;
uint8_t scrollPosition = 0;

void clearSecondRow() {
  lcd.setCursor(0, 1);
  lcd.print("                ");
}

void showTemperature(float temperatureC) {
  clearSecondRow();
  lcd.setCursor(0, 1);
  lcd.print("Temp: ");
  lcd.print(temperatureC, 1);
  lcd.write(byte(223));  // Degree symbol on common HD44780 LCDs.
  lcd.print("C");
}

void showSensorError() {
  clearSecondRow();
  lcd.setCursor(0, 1);
  lcd.print("Sensor error");
}

void showScrollingName() {
  const uint8_t nameLength = sizeof(STUDENT_NAME) - 1;

  lcd.setCursor(0, 0);

  if (nameLength <= LCD_COLUMNS) {
    lcd.print(STUDENT_NAME);
    for (uint8_t i = nameLength; i < LCD_COLUMNS; i++) {
      lcd.print(' ');
    }
    return;
  }

  const uint8_t cycleLength = nameLength + NAME_GAP;

  for (uint8_t column = 0; column < LCD_COLUMNS; column++) {
    uint8_t index = (scrollPosition + column) % cycleLength;
    lcd.print(index < nameLength ? STUDENT_NAME[index] : ' ');
  }

  scrollPosition = (scrollPosition + 1) % cycleLength;
}

void readDisplayAndSendTemperature() {
  float temperatureC = dht.readTemperature();

  if (isnan(temperatureC)) {
    showSensorError();
    Serial.println("ERROR:DHT11_READ_FAILED");
    return;
  }

  showTemperature(temperatureC);

  // Serial protocol: ASCII text, one message per line.
  // Example: TEMP:25.00
  Serial.print("TEMP:");
  Serial.println(temperatureC, 2);
}

void setup() {
  Serial.begin(9600);
  dht.begin();

  lcd.init();
  lcd.backlight();
  lcd.clear();

  showScrollingName();
  clearSecondRow();
  lcd.setCursor(0, 1);
  lcd.print("Starting DHT11");

  Serial.println("STATUS:Arduino DHT11 temperature monitor started");

  // Give the DHT11 time to stabilize before its first reading.
  delay(2000);
  readDisplayAndSendTemperature();

  lastTemperatureTime = millis();
  lastScrollTime = millis();
}

void loop() {
  unsigned long now = millis();

  if (now - lastScrollTime >= SCROLL_INTERVAL_MS) {
    lastScrollTime = now;
    showScrollingName();
  }

  if (now - lastTemperatureTime >= TEMPERATURE_INTERVAL_MS) {
    lastTemperatureTime = now;
    readDisplayAndSendTemperature();
  }
}
