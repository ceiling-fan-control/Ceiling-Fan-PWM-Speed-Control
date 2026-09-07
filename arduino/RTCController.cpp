
#include "RTCController.h"

RTCController::RTCController() {
  Serial.println("rtc controller init");

  if (! rtc.begin()) {
    Serial.println("Couldn't find RTC");
    while (1);
  }

  if (rtc.lostPower()) {
    Serial.println("RTC lost power, lets set the time!");
//     following line sets the RTC to the date & time this sketch was compiled
//    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
//     This line sets the RTC with an explicit date & time, for example to set
//     January 21, 2014 at 3am you would call:
     rtc.adjust(DateTime(2014, 1, 21, 3, 0, 0));
  }

  setSyncProvider(syncProvider);   // the function to get the time from the RTC //TODO should be  setSyncProvider(syncProvider);   
  if (timeStatus() != timeSet)
    Serial.println("Unable to sync with the RTC");
  else
    Serial.println("RTC has set the system time");
  setSyncInterval(10000); // set the number of seconds between re-sync of time

}

void RTCController::adjustRTC(StringSplitter *command) {
  int Year = command->getItemAtIndex(0).toInt();
  int Month = command->getItemAtIndex(1).toInt();
  int Day = command->getItemAtIndex(2).toInt();
  int Hour = command->getItemAtIndex(3).toInt();
  int Minute = command->getItemAtIndex(4).toInt();
  int Second = command->getItemAtIndex(5).toInt();
  rtc.adjust(DateTime(Year, Month, 1, Hour, Minute, Second));
}

void RTCController::printTime() {
  DateTime now = rtc.now();
  Serial.print(now.year(), DEC);
  Serial.print('/');
  Serial.print(now.month(), DEC);
  Serial.print('/');
  Serial.print(now.day(), DEC);
  Serial.print(" (");
  Serial.print(now.hour(), DEC);
  Serial.print(':');
  Serial.print(now.minute(), DEC);
  Serial.print(':');
  Serial.print(now.second(), DEC);
  Serial.println();
}

String RTCController::timeString() {
  DateTime now = rtc.now();

  String sender = "Date: ";
  sender += String(now.year(), DEC) + "/" + String(now.month(), DEC) + "/" + String(now.day(), DEC);
  sender += "   " + String(now.hour(), DEC) + ":" + String(now.minute(), DEC) + ":" + String(now.second(), DEC);

  return sender;
}

String static RTCController::time_tReadable(time_t t) {

  String sender = String(hour(t), DEC) + ":";
  sender += String(minute(t), DEC) + ":";
  sender += String(second(t), DEC);

  return sender;
}

uint32_t static RTCController::syncProvider() { //function which sets up the RTC as the source of external time
  return rtc.now().unixtime();
}
