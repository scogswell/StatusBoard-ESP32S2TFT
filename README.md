# A status display with Circuitpython you can update from remote and isn't the MagTag.

This project shows that the MagTag status board https://github.com/scogswell/Magtag-status-board can be adapted to easily run on other ESP32 hardware.  In this case an ESP32S2-TFT.  https://www.adafruit.com/product/5300 . 

Differences from the MagTag version:
- No deep sleep, since the TFT turns off.  Hence it stay on all the time and will consume much more power from a battery than the MagTag.  I get 7-8 hours out of a 900 mAh battery.  Plug it in for best results
- Since no deep sleeping, uses subcribe in MQTT to update status very fast.  
- Tiny display almost useless as an actual status board, but it's the thought that counts. 
- Gets time from NTP.  
- Gets battery stats directly from the LC chip on the ESP32-S2 TFT.  

These libraries are in /lib:
```
adafruit_bitmap_font, adafruit_display_text, adafruit_imageload, adafruit_io
adafruit_minimqtt, adafruit_fakerequests, adafruit_lc709203f, adafruit_ntp,
adafruit_requests, neopixel, simpleio
```