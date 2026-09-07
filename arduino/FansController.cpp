
#include "FansController.h"

FansController::FansController() {
  Serial.println("fans controller init");
  //set fan control pin
  pinMode(FAN_PIN, OUTPUT);

}


static void FansController::on() {
  fan(255);
}

static void FansController::off() {
  fan(0);
}


static void FansController::fan(int speed_) {
  fanOn = (speed_ > 0);
  speed = speed_;
  analogWrite(FAN_PIN, speed_);
}

void FansController::getSpeed() {
  return speed;
}


void FansController::onOff() {
  oldSpeed = speed;
  if (fanOn) {
    off();
  } else {
    on();
  }
  onOfEnabled = true;
  onOfTimer = millis();
}

void FansController::loop() {

  if (onOfEnabled && onOfTimer + INBETWEEN_ON_OF < millis()) {
    onOfEnabled = false;
    fan(oldSpeed);//reset to previous state
  }

}



