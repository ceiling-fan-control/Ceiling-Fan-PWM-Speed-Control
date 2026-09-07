#include <Wire.h>
#include <Adafruit_RGBLCDShield.h>
#include <utility/Adafruit_MCP23017.h>
#include <dht.h>
#include <IRremote.h>

// Pins
#define DHT_P 4
#define IR_P 2
#define THERM_P 0
#define transistorPin 6

// Constants
#define UPPER_FAN_LIMIT 9
#define FAN_BAR_INDEX 14

// Creation of elements
dht DHT;
Adafruit_RGBLCDShield lcd = Adafruit_RGBLCDShield();
IRrecv irrecv(IR_P);
decode_results results;

////// Custom characters for the LCD display.
const uint8_t cFanCharacterMask[] PROGMEM = {
  0b01100,
  0b01100,
  0b00101,
  0b11011,
  0b11011,
  0b10100,
  0b00110,
  0b00110,
};
const char cFanCharacter = '\x05';
const uint8_t cTemp1CharacterMask[] PROGMEM = {
  0b01000,
  0b10100,
  0b10100,
  0b10100,
  0b10100,
  0b11101,
  0b11101,
  0b01000
};
const char cTemp1Character = '\x06';
const uint8_t cTemp2CharacterMask[] PROGMEM = {
  0b01000,
  0b10101,
  0b10101,
  0b10100,
  0b10100,
  0b11101,
  0b11101,
  0b01000
};
const char cTemp2Character = '\x07';
////// END Custom characters for the LCD display.

//// Variable creation
int fanSpeed = 4;
char tempUnit = 'F';

long start_DHT = -1;
long start_DisplayChange = -1;
long start_IR = -1;
long start_scroll = -1;

int Vo;
float R1 = 10000;
float logR2, R2, T;
float CT1, FT1, CT2, FT2;
float c1 = 1.009249522e-03, c2 = 2.378405444e-04, c3 = 2.019202697e-07;

int celTemp = 0;
float multiplier = (9.0 / 5.0);
int fahTemp = 0;

String lastCommand;
String current_time = "";
String message = "";
String serial_read = "";

int message_index = 0;
int scroll_delay = 2000;
//// END Variable creation

//// Setup function
void setup() {
  // Begin serial communication at 9600 baud
  Serial.begin(9600);
  
  // Prevents whining of fans
  setPwmFrequency(transistorPin, 8);
  lcd.begin(16, 2);
  irrecv.enableIRIn();
  irrecv.blink13(true);

  // Add custom characters for the fan as bar display.
  uint8_t bars[] = {B10000, B11000, B11100, B11110, B11111};
  uint8_t character[8];
  for (uint8_t i = 0; i < 5; ++i) {
    for (uint8_t j = 0; j < 8; ++j) character[j] = bars[i];
    lcd.createChar(i, character);
  }
  // Add custom characters from the masks.
  memcpy_P(character, cFanCharacterMask, 8);
  lcd.createChar(cFanCharacter, character);
  memcpy_P(character, cTemp1CharacterMask, 8);
  lcd.createChar(cTemp1Character, character);
  memcpy_P(character, cTemp2CharacterMask, 8);
  lcd.createChar(cTemp2Character, character);

  // Setup the transistor pin as output
  pinMode(transistorPin, OUTPUT);

  // Get the initial data
  sampleData(celTemp, fahTemp);

  // Update the display with the data
  updateDisplay();

  // Update the display with the fan speed
  updateFanDisplay(fanSpeed);
}

// Print to the LCD the fan speed (denoted by varying sizes of bars)
void updateFanDisplay (int rate) {
  lcd.setCursor(FAN_BAR_INDEX,0);
  if (rate > 4) {
    lcd.print(static_cast<char>(4));
    int tempFanSpeed = rate - 4;
    lcd.print(static_cast<char>(tempFanSpeed-1));
  } else {
    lcd.print(static_cast<char>(rate));
    lcd.print(' ');
  }
}

// This function handles operations by the user using the IR remote.
// Updates the display if necessary for the changed operation.
void changeMode (String irVal, int & fanSpeed) {
  int speedBefore = fanSpeed;
  
  if (irVal == "ff18e7") {
    if (fanSpeed != UPPER_FAN_LIMIT) {
      fanSpeed++;
    }
  } else if (irVal == "ff4ab5") {
    if (fanSpeed != 0) {
      fanSpeed--;
    }
  }
  if (fanSpeed != speedBefore) {
    updateFanDisplay(fanSpeed);
  }

  if (irVal == "ffa25d") {
    tempUnit = 'F';
    updateDisplay();
  }
  if (irVal == "ff629d") {
    tempUnit = 'C';
    updateDisplay();
  }
  start_IR = millis();
}

void scroll_message () {
  String sub_message = message.substring(message_index, message_index + 16);
  lcd.setCursor(0,1);
  lcd.print(sub_message);

  message_index = message_index + 2;

  if (message_index > (message.length() - 15)) {
    message_index = 0;
    scroll_delay = 5000;
    return;
  }
  if (message_index > 3) {
    scroll_delay = 2000;
  }
}

// General display creation and population function.
// Adds the time, system air temperature, and fan character.
void updateDisplay () {
  lcd.clear();
  lcd.setCursor(0,0);
  lcd.print(current_time);
  lcd.setCursor(current_time.length() + 1,0);
  lcd.print(cTemp1Character);
  if (tempUnit == 'F') {
    lcd.print(fahTemp, DEC);
    lcd.print('\xdf');
    lcd.print("F ");
  } else {
    lcd.print(celTemp, DEC);
    lcd.print('\xdf');
    lcd.print("C ");
  }
  // No need for humidity values
//  lcd.print(static_cast<uint8_t>(DHT.humidity), DEC);
//  lcd.print('%');
  lcd.setCursor(FAN_BAR_INDEX-1,0);
  lcd.print(cFanCharacter);
  updateFanDisplay(fanSpeed);
  lcd.setCursor(0,1);
//  lcd.print(message);
}

// Reads the temperature from the DHT sensor, stores it if it successfully read.
// Reads from the thermistor and updates the display only if the averages changed.
void sampleData (int & celTemp, int & fahTemp) {
  // Attempt to read from the DHT sensor
  int chk = DHT.read11(DHT_P);
  if (chk == 0) {
    CT1 = DHT.temperature;
    float celMult = CT1 * multiplier;
    FT1 = celMult + 32;
  }

  // Read from the thermistor
  Vo = analogRead(THERM_P);
  R2 = R1 * (1023.0 / (float)Vo - 1.0);
  logR2 = log(R2);
  T = (1.0 / (c1 + c2*logR2 + c3*logR2*logR2*logR2));
  CT2 = T - 273.15;
  FT2 = (CT2 * 9.0)/ 5.0 + 32.0;

  // Cache the values
  int celTempCache = celTemp;
  int fahTempCache = fahTemp;

  // Average the temperatures or just use the thermistor
  // values if DHT was unsuccessful
  if (chk == 0) {
    celTemp = (int)((CT1 + CT2) / 2);
    fahTemp = (int)((FT1 + FT2) / 2);
  } else {
    celTemp = (int)CT2;
    fahTemp = (int)FT2;
  }

  // If the values changed, update the display
  if (celTempCache != celTemp || fahTempCache != fahTemp) {
    updateDisplay();
  }

  // Mark when it was last sensed
  start_DHT = millis();
}

/**
 * Divides a given PWM pin frequency by a divisor.
 * 
 * The resulting frequency is equal to the base frequency divided by
 * the given divisor:
 *   - Base frequencies:
 *      o The base frequency for pins 3, 9, 10, and 11 is 31250 Hz.
 *      o The base frequency for pins 5 and 6 is 62500 Hz.
 *   - Divisors:
 *      o The divisors available on pins 5, 6, 9 and 10 are: 1, 8, 64,
 *        256, and 1024.
 *      o The divisors available on pins 3 and 11 are: 1, 8, 32, 64,
 *        128, 256, and 1024.
 * 
 * PWM frequencies are tied together in pairs of pins. If one in a
 * pair is changed, the other is also changed to match:
 *   - Pins 5 and 6 are paired on timer0
 *   - Pins 9 and 10 are paired on timer1
 *   - Pins 3 and 11 are paired on timer2
 * 
 * Note that this function will have side effects on anything else
 * that uses timers:
 *   - Changes on pins 3, 5, 6, or 11 may cause the delay() and
 *     millis() functions to stop working. Other timing-related
 *     functions may also be affected.
 *   - Changes on pins 9 or 10 will cause the Servo library to function
 *     incorrectly.
 * 
 * Thanks to macegr of the Arduino forums for his documentation of the
 * PWM frequency divisors. His post can be viewed at:
 *   http://forum.arduino.cc/index.php?topic=16612#msg121031
 */
void setPwmFrequency(int pin, int divisor) {
  byte mode;
  if(pin == 5 || pin == 6 || pin == 9 || pin == 10) {
    switch(divisor) {
      case 1: mode = 0x01; break;
      case 8: mode = 0x02; break;
      case 64: mode = 0x03; break;
      case 256: mode = 0x04; break;
      case 1024: mode = 0x05; break;
      default: return;
    }
    if(pin == 5 || pin == 6) {
      TCCR0B = TCCR0B & 0b11111000 | mode;
    } else {
      TCCR1B = TCCR1B & 0b11111000 | mode;
    }
  } else if(pin == 3 || pin == 11) {
    switch(divisor) {
      case 1: mode = 0x01; break;
      case 8: mode = 0x02; break;
      case 32: mode = 0x03; break;
      case 64: mode = 0x04; break;
      case 128: mode = 0x05; break;
      case 256: mode = 0x06; break;
      case 1024: mode = 0x07; break;
      default: return;
    }
    TCCR2B = TCCR2B & 0b11111000 | mode;
  }
}
//end arduino code

// Arduino main loop function
void loop() {
  // Attempt to read from the serial port and store the characters in serial_read
  if (Serial.available() > 0) {
    int incomingByte = Serial.read();
    char char_rec = (char)incomingByte;
    serial_read = serial_read + char_rec;
  }

  // Check to see if we encountered an end delimiter, if so do an operation with the data.
  if (serial_read[serial_read.length()-1] == ';' && serial_read[0] == '&') {
    // ';' is the delimiter indicating a change in fan speed, get the value and change the fanSpeed variable
    String serial_read_num = serial_read.substring(1, serial_read.length() - 1);
    fanSpeed = serial_read_num.toInt();
    updateFanDisplay(fanSpeed);
    serial_read = "";
    serial_read_num = "";
  } else if (serial_read[serial_read.length()-1] == '%' && serial_read[0] == '&') {
    // '%' is the delimiter for the time, set the current_time variable and update the display
    current_time = serial_read.substring(1, serial_read.length() - 1);
    serial_read = "";
    updateDisplay();
  } else if (serial_read[serial_read.length()-1] == '^' && serial_read[0] == '&') {
    // '^' is the delimiter for the temperature unit, set the temperature unit to what was sent
    tempUnit = serial_read.charAt(1);
    serial_read = "";
    updateDisplay();
  } else if (serial_read[serial_read.length()-1] == '#' && serial_read[0] == '&') {
    // 
    message_index = 0;
    scroll_delay = 2000;
    message = serial_read.substring(1, serial_read.length() - 1);
    if ((message.length() % 2) == 1) {
      message = message + " ";
    }
    serial_read = "";
    updateDisplay();
  } else {
    if (serial_read[0] != '&') {
      serial_read = "";
    }
  }

  // Handle IR remote input
  if (irrecv.decode(&results) && (millis() > (50+start_IR) || start_IR == -1)) {
    String value;
    if (results.value == 0xFFFFFFFF) {
      value = lastCommand;
    } else {
      lastCommand = String(results.value, HEX);
      value = String(results.value, HEX);
    }
    changeMode(value, fanSpeed);
    irrecv.resume();
  }

  // Check the current time against the operations that happen every X milliseconds
  // Start the operations if it is time
  unsigned long currTime = millis();
  if (start_DHT != -1 && currTime >= (start_DHT + 2000)) {
    sampleData(celTemp, fahTemp);
  }
  if (currTime >= (start_scroll + scroll_delay)) {
    start_scroll = millis();
    scroll_message();
  }
  if (start_DisplayChange != -1 && currTime >= (start_DisplayChange + 1000)) {
    updateDisplay();
    start_DisplayChange = -1;
  }

  // Convert the fan speed to a PWM value and write that value to the PWM pins
  int temp_fanSpeed = 10 - fanSpeed;
  int outputValue = map(temp_fanSpeed, 1, 10, 0, 255);
  analogWrite(transistorPin, outputValue);
}
