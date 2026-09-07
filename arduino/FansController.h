
#ifndef FansController_h
#define FansController_h

#include "Arduino.h"

#define FAN_PIN 10 //pin A2

class FansController {
  private:
    
    unsigned long onOfTimer;
    const int INBETWEEN_ON_OF = 300;
    boolean onOfEnabled;
  public:
    FansController();
    static boolean fanOn;
    int oldSpeed;
    static void on();
    static void off();
    static void callback();
    static void setSpeed(int _speed);
    static void getSpeed();
    static int speed;
    static void fan(int speed);
    void loop();
    void onOff();
    
};


#endif


