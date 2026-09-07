

#include "BluetoothController.h"
BluetoothController *bluetoothController;

int FansController::speed = 0;
boolean FansController::fanOn = false;

void setup() {
setPwmFrequency(10, 1);
  Serial.begin(9600);
   while (!Serial){
    Serial.println("waiting for serial");
   }
   Serial.println("Start program");
   bluetoothController = new BluetoothController();
  
}


void loop() {
  bluetoothController->loopBluetooth();
  //Serial.println(freeRam()); //memory leak checker
  
}

int freeRam ()
{
extern int __heap_start, *__brkval;
int v;
return (int) &v - (__brkval == 0 ? (int) &__heap_start : (int) __brkval);
}

void setPwmFrequency(int pin, int divisor) {//TODO clean up for only 10
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








