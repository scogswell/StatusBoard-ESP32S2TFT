#
# The Statusboard as proof of concept will run on other ESP32 hardware
# besides the MagTag.  See more detail at:
#  https://github.com/scogswell/Magtag-status-board
#
# Note that the ESP32S2-TFT will turn off the TFT during deep sleep so
# we don't do deep sleep here.  We also use MQTT listeners so
# statuses update as fast as possible.
# Either plug it into power or have a battery you plan to charge every night.
# With a 900mAh battery I get about 7-8 hours runtime.
#
# These libraries are in /lib:
# adafruit_bitmap_font, adafruit_display_text, adafruit_imageload, adafruit_io
# adafruit_minimqtt, adafruit_fakerequests, adafruit_lc709203f, adafruit_ntp,
# adafruit_requests, neopixel, simpleio
#
import ssl
import wifi
import socketpool
import adafruit_requests as requests
import secrets
import time
import terminalio
from adafruit_display_text import label, wrap_text_to_pixels
from adafruit_bitmap_font import bitmap_font
import microcontroller
import espidf
import wifi_select
import neopixel
import board
import displayio
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_io.adafruit_io import IO_MQTT
import adafruit_ntp
import rtc
from adafruit_lc709203f import LC709203F
import digitalio

DEBUG = True
SLEEP_TIME = 1*60   # in seconds
STATUS_FEED = "status"
my_tz_offset = -4

BATTERY_UPDATE = 60
SHOW_BATTERY = False

# enable ability to turn the neopixel power off
pixel_power = digitalio.DigitalInOut(board.NEOPIXEL_POWER)
pixel_power.switch_to_output(value=True)
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
# Damn those neopixels are bright.
pixel.brightness=0.05
pixel.auto_write=True

# The TFT display
display = board.DISPLAY
display_group = displayio.Group()

# i2c for the battery sensor
i2c = board.I2C()  # uses board.SCL and board.SDA

def battery_display():
    if SHOW_BATTERY:
        batt_text = "{:.1f} %".format(battery_sensor.cell_percent)
    else:
        batt_text = ""
    if battery_sensor.cell_percent < 10:
        batt_text += " Battery Low"
    return batt_text

def error_message(s):
    """ Quick helper function to show error messages on the TFT screen"""
    s += "\nRebooting..."
    error_group = displayio.Group()
    M_SCALE_TEXT = 2
    font = terminalio.FONT
    M_WRAP_WIDTH = display.width/M_SCALE_TEXT
    message_label = label.Label(font=font,scale=M_SCALE_TEXT,color=0xFF0000,line_spacing=1.0)
    message_label.anchor_point=(0,0)
    message_label.anchored_position=(0,0)
    message_label.text = "\n".join(wrap_text_to_pixels(s, M_WRAP_WIDTH,font))
    error_group.append(message_label)
    display.show(error_group)
    display.refresh()

# Define callback functions which will be called when certain events happen.
def io_connected(client):
    print("Connected to Adafruit IO!")
    client.subscribe(STATUS_FEED)

def io_message(client, feed_id, payload):  # pylint: disable=unused-argument
    print("Feed {0} received new value: {1}".format(feed_id, payload))
    if feed_id == "status":
        # Make new status box with font scaled to fit big as possible
        status_label = fit_text_box(payload)
        # Get rid of old status display
        display_group.pop()
        display_group.append(status_label)
        time_label.text = format_datetime(time.localtime())

def fit_text_box(the_text):
    # Loop through the fonts we've pre-compiled and listed.  Start with the biggest and if the text from the Status fits
    # display it on screen.  Otherwise move to the next size (smaller) and try again.  Keep trying until we run out of
    # fonts and just use the smallest one.  Using native font sizes looks much better on the e-ink than using
    # label scales.
    for f in theFonts:
        time_height = time_label.bounding_box[3]
        print("Trying font",f)
        font = bitmap_font.load_font(f)

        the_text = the_text.strip()
        status_label = label.Label(font=font, text=the_text, color=0xFFFF00,scale=1,line_spacing=1.0)
        status_label.anchored_position = (display.width/2, (display.height-time_height)/2)
        status_label.anchor_point = (0.5, 0.5)

        WRAP_WIDTH = display.width
        print("Width is",display.width,"Height is",display.height, "Scale Width is",WRAP_WIDTH, "Available Height is",display.height-time_height)

        if " " in the_text:
            status_label.text = "\n".join(wrap_text_to_pixels(the_text, WRAP_WIDTH,font))
        else:
            status_label.text = the_text
        # How big was that label we just made?
        dims = status_label.bounding_box
        print("Box fits in Width ",dims[2]," Height ",dims[3])
        # If this box actually fits on the screen, let's use it
        if dims[2] < display.width and dims[3] < display.height-time_height:
            print("proper fit")
            break
    print("Found Font that fits screen")
    return status_label

def format_datetime(datetime):
    """
    Simple pretty-print for a datetime object
    """
    # pylint: disable=consider-using-f-string
    if datetime.tm_hour > 12:
        ampm_hour = datetime.tm_hour - 12
        ampm_text = "PM"
    else:
        ampm_hour = datetime.tm_hour
        ampm_text = "AM"
    return "{:02}/{:02}/{} {:02}:{:02}:{:02} {}".format(
        datetime.tm_mon,
        datetime.tm_mday,
        datetime.tm_year,
        ampm_hour,
        datetime.tm_min,
        datetime.tm_sec,
        ampm_text,
    )

# Precompiled fonts, from largest size to smallest.   The status message will
# try them in sequence until the status box fits on the screen.
theFonts = ['fonts/FreeSans-96.pcf','fonts/FreeSans-84.pcf','fonts/FreeSans-72.pcf',
            'fonts/FreeSans-48.pcf','fonts/FreeSans-36.pcf','fonts/FreeSans-24.pcf',
            'fonts/FreeSans-18.pcf','fonts/FreeSans-16.pcf','fonts/FreeSans-12.pcf']

# Get secrets for wifi/adafruit io/etc.
try:
    from secrets import secrets as secrets_many
except ImportError:
    print("WiFi and Adafruit IO credentials are kept in secrets.py - please add them there!")
    error_message("WiFi and Adafruit IO credentials are kept in secrets.py - please add them there!")
    raise

# Find a wifi network in range that's listed in the secrets file
try:
    secrets = wifi_select.select_wifi_network(secrets_many)
except Exception as e:
    print("Error scanning for wifi networks",e)
    error_message("Error scanning for wifi networks")
    time.sleep(5)
    microcontroller.reset()

print("My MAC addr:", [hex(i) for i in wifi.radio.mac_address])

# Figure out if we're using Enterprise WiFi or regular WPA password Wifi
if 'username' in secrets:
    if wifi_select.enterprise_wifi_available():
        print("Changing enterprise to True")
        wifi.radio.enterprise = True
        wifi.radio.set_enterprise_id(identity=secrets['identity'],username=secrets['username'],password=secrets['password'])
    else:
        print("Cannot connect to Enterprise WiFi with this version of CircuitPython")
        error_message("This Circuitpython doesn't support WPA Enterprise")
        raise ConnectionError
else:
    if wifi_select.enterprise_wifi_available():
        print("Changing enterprise to False")
        wifi.radio.enterprise = False

# Connect to WiFi
pixel[0]=(0,0,255)
try:
    print("Connecting to {}".format(secrets["ssid"]))
    if wifi_select.enterprise_wifi_available() and wifi.radio.enterprise:
        wifi.radio.connect(secrets["ssid"],timeout=60)
    else:
        wifi.radio.connect(secrets["ssid"], secrets["password"])
    print("Connected to %s!" % secrets["ssid"])
    pixel[0]=(0,255,0)
# Wi-Fi connectivity fails with error messages, not specific errors, so this except is broad.
except Exception as e:  # pylint: disable=broad-except
    print("ESPIDF Heap caps free: ", espidf.heap_caps_get_free_size())
    print("ESPIDF largest block : ", espidf.heap_caps_get_largest_free_block())
    print("Failed to connect to WiFi. Error:", e, "\nBoard will hard reset in 10 seconds.")
    pixel[0]=((255,0,0))
    error_message("Can't connect to Wifi {}".format(secrets["ssid"]))
    time.sleep(5)
    microcontroller.reset()
print("ESPIDF Heap caps free: ", espidf.heap_caps_get_free_size())
print("ESPIDF largest block : ", espidf.heap_caps_get_largest_free_block())
print("Connected to %s "%secrets["ssid"])
print("My IP address is", wifi.radio.ipv4_address)

pool = socketpool.SocketPool(wifi.radio)

# Set time from NTP.
# https://github.com/todbot/circuitpython-tricks#set-rtc-time-from-ntp
ntp = adafruit_ntp.NTP(pool, tz_offset=my_tz_offset)
rtc.RTC().datetime = ntp.datetime
print("current datetime:", format_datetime(time.localtime()))

pixel[0]=(255,255,0)
# Initialize a new MQTT Client object
mqtt_client = MQTT.MQTT(
    broker="io.adafruit.com",
    username=secrets["aio_username"],
    password=secrets["aio_key"],
    socket_pool=pool,
    ssl_context=ssl.create_default_context(),
)
# Initialize Adafruit IO MQTT "helper"
io = IO_MQTT(mqtt_client)

# Set up the callback methods above
io.on_connect = io_connected
io.on_message = io_message

# Label for time along the bottom of the screen
timeFont = terminalio.FONT
time_label = label.Label(font=timeFont,text=format_datetime(time.localtime()),color=0xFFFFFF,scale=1,line_spacing=1.0)
time_label.anchored_position = (display.width/2, display.height)
time_label.anchor_point = (0.5, 1.0)

battery_sensor = LC709203F(i2c)
print("Battery IC version:", hex(battery_sensor.ic_version))

# Label for battery voltage display
battery_label = label.Label(font=timeFont,text=battery_display(),color=0xFFFFFF,scale=1,line_spacing=1.0)
battery_label.anchored_position = (0,0)
battery_label.anchor_point = (0,0)

status_label = fit_text_box("Connecting...")

display_group.append(time_label)
display_group.append(battery_label)
display_group.append(status_label)

display.show(display_group)
display.refresh()

battery_update_time = time.monotonic()
# Turn off neopixel
pixel[0]=(0,255,0)
pixel_power.switch_to_output(value=False)
while True:
    try:
        # If Adafruit IO is not connected...
        if not io.is_connected:
            # Connect the client to the MQTT broker.
            print("Connecting to Adafruit IO...")
            io.connect()
            # Initially refresh the feed
            io.get(STATUS_FEED)

        # Explicitly pump the message loop.
        io.loop()

        if (time.monotonic() > battery_update_time + BATTERY_UPDATE):
            battery_label.text=battery_display()

            battery_update_time = time.monotonic()

    # Adafruit IO fails with internal error types and WiFi fails with specific messages.
    # This except is broad to handle any possible failure.
    except Exception as e:  # pylint: disable=broad-except
        print("Failed to get or send data, or connect. Error:", e,
              "\nBoard will hard reset in 10 seconds.")
        error_message("Failed to get data from Adafruit IO")
        time.sleep(5)
        microcontroller.reset()

    time.sleep(10)