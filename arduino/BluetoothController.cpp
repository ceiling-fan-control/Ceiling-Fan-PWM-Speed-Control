#include "BluetoothController.h"

BluetoothController::BluetoothController() {
  Serial.println("bluetooth controller init");
  bluetoothSerial->begin(9600);
}

void BluetoothController::loopBluetooth() {

  if (bluetoothSerial->available()) {
    inbetweenTime = millis();
    bluetoothCommunication = true;
    Serial.println(bluetoothSerial->peek());
    bluetoothRead.concat((char)bluetoothSerial->read());
  }

  if (bluetoothCommunication && millis() > (NO_COMMUNICATION_TIME + inbetweenTime)) {
    Serial.println("communication done");
    bluetoothRead.trim();
    Serial.println(bluetoothRead);
    action(bluetoothRead);
    bluetoothRead = "";
    bluetoothCommunication = false;
  }

  if (Serial.available()) {
    bluetoothSerial->write(Serial.read());//comunicate to bluetoothchip
  }

  if (bluetoothCommunication) { //if there is bluetooth comminication dont sleep for a second
    alarmController.delay(0);
  } else {
    //rtcController.printTime();
    alarmController.delay(0);
  }
  alarmController.loop();
}


void BluetoothController::action(String input)
{
  if (input.equals(OK_CONN)) {
    alarmController.manualFanOnOff();//turn off and on the fan for show
    input = input.substring(OK_CONN.length()); //ok_conn does not have an line ending thus can hold also another command
    Serial.println("input after ok " + input);
  }
  
  else if (input.equals(GET_INFO)) {
    Serial.println("send info");
    bluetoothSerial->println(GET_TIME + "+" + rtcController.timeString());
    bluetoothSerial->println(GET_FAN_ON + "+" + (String)FansController::fanOn);
    //bluetoothSerial->println(FAN_SPEED + (String)alarmController.fansController.getSpeed());
    bluetoothSerial->println(MAX_FANS + "+" + dtNBR_ALARMS);
    bluetoothSerial->println(AMOUNT_FANS + "+" + (String)alarmController.count());

    for (int ID = 0; ID < dtNBR_ALARMS; ID++) {
      bluetoothSerial->println(alarmController.alarmInfo(ID));

    }
    bluetoothSerial->println(rtcController.timeString());

  }
  else if (input.equals(FAN_ON)) {
    alarmController.manualFanOn();
    bluetoothSerial->println(FAN_ON + OK_RESULT);
  }
  else if (input.equals(FAN_OFF))
  {
    alarmController.manualFanOff();
    bluetoothSerial->println(FAN_OFF + OK_RESULT);
  }else if(input.equals(GET_FAN_ON)){
    bluetoothSerial->println(FansController::fanOn);
  }
  else if (input.equals(MAX_FANS))
  {
    bluetoothSerial->println(MAX_FANS + "+" + dtNBR_ALARMS);
  }
  else if (input.equals(AMOUNT_FANS))
  {
    bluetoothSerial->println(AMOUNT_FANS + "+" + alarmController.count());
  }
  else if (input.equals(GET_TIME))
  {
    String result = rtcController.timeString();
    bluetoothSerial->println(result);
  }
  else if (input.equals(GET_FANS))
  {
    for (int ID = 0; ID < dtNBR_ALARMS; ID++) {
      bluetoothSerial->println(alarmController.alarmInfo(ID));
    }
  }
  else if (input.substring(0, SET_FAN.length()).equals(SET_FAN))
  {
    String commandString = input.substring(SET_FAN.length());
    Serial.println(commandString);
    StringSplitter *command = new StringSplitter(commandString, ':', 6);

    int code = alarmController.setAlarm(command);

    if (code == -1) {
      bluetoothSerial->println(SET_FAN + ERROR_RESULT);
    } else if (code == -2) {
      bluetoothSerial->println(SET_FAN + MAX_FANS_RESULT);
    } else {
      bluetoothSerial->println(alarmController.alarmInfo(code));
    }
    delete command;
    command = NULL;
  }
  else if (input.substring(0, SET_FAN.length()).equals(SET_FAN))
  {
    String commandString = input.substring(SET_FAN.length());
    StringSplitter *command = new StringSplitter(commandString, ':', 6);

    int code = alarmController.setAlarm(command);
    String result = fanCodeToString(code);
    bluetoothSerial->println(result);
    delete command;
    command = NULL;
  }
  else if (input.substring(0, SET_TIMER_FAN.length()).equals(SET_TIMER_FAN))
  {
//    String commandString = input.substring(SET_TIMER_FAN.length());
//    StringSplitter *command = new StringSplitter(commandString, ':', 6);
//
//    int code = alarmController.setTimer(command);
//    String result = fanCodeToString(code);
//    bluetoothSerial->println(result);
//    delete command;
//    command = NULL;
  }
  else if (input.substring(0, REMOVE_FANS.length()).equals(REMOVE_FANS))
  {
    alarmController.removeAlarms();
    bluetoothSerial->println(REMOVE_FANS + OK_RESULT);
  }
  else if (input.substring(0, REMOVE_FAN.length()).equals(REMOVE_FAN))
  {
    String commandString = input.substring(REMOVE_FAN.length());
    int ID = commandString.toInt();
    alarmController.removeAlarm(ID);

    bluetoothSerial->println(REMOVE_FAN + ID + OK_RESULT);
  }

  else if (input.substring(0, SET_TIME.length()).equals(SET_TIME))
  {
    String commandString = input.substring(SET_TIME.length());
    StringSplitter *command = new StringSplitter(commandString, ':', 7);
    rtcController.adjustRTC(command);
    String result = rtcController.timeString();
    bluetoothSerial->println(result);
    delete command;
    command = NULL;
  }
  else
  {
    bluetoothSerial->println("unknown command");
  }
}

String BluetoothController::fanCodeToString(int code) {
  if (code == -1) {
    bluetoothSerial->println(SET_FAN + ERROR_RESULT);
  } else if (code == -2) {
    bluetoothSerial->println(SET_FAN + MAX_FANS_RESULT);
  } else {
    bluetoothSerial->println(SET_FAN + OK_RESULT + "+" + alarmController.alarmInfo(code));
  }
}




