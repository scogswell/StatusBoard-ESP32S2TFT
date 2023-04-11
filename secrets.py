# SPDX-FileCopyrightText: 2020 Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

# This file is where you keep secret settings, passwords, and tokens!
# If you put them in the code you risk committing that info or sharing it

# This works with the wifi_select.py functions.  You can put several wifi
# networks settings and wifi_select will pick the first one that's available.
# Nice if you have to move locations with your device.
secrets = []

secrets.append ({
    'ssid' : 'my-ssid',
    'password' : 'my-password',
    'aio_username' : 'my-adafruit-io-user',
    'aio_key' : 'my-adafruit-io-key',
    'timezone' : "America/NewYork", # http://worldtimeapi.org/timezones
    })

secrets.append ({
    'ssid' : 'my-ssid-2',
    'password' : 'my-password',
    'aio_username' : 'my-adafruit-io-user',
    'aio_key' : 'my-adafruit-io-key',
    'timezone' : "America/NewYork", # http://worldtimeapi.org/timezones
    })