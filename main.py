"""
smart_trashbin.py
=================
MicroPython firmware for an ESP32-based smart trashbin.

Features
--------
- Ultrasonic sensor to measure fill level
- DHT22 sensor for temperature and humidity monitoring
- Servo motor to open/close the lid remotely
- LED alert for high fill level or liquid detection
- MQTT integration for remote control and status reporting

MQTT Dashboard (to view messages):
    https://mqtt-dashboard.com/

Topics
------
- Receive commands : lixeira/comandos
- Send status      : lixeira/status

Supported commands
------------------
- ``tabre``  — open the lid
- ``tfecha`` — close the lid
- ``lon``    — turn LED on
- ``loff``   — turn LED off
"""

import time
from machine import Pin, PWM, reset  # type: ignore

import network        # type: ignore  (MicroPython built-in)
import dht            # type: ignore  (MicroPython built-in)
from umqtt.simple import MQTTClient  # type: ignore


# ---------------------------------------------------------------------------
# MQTT configuration
# ---------------------------------------------------------------------------

MQTT_CLIENT_ID = "FILL"                       # Unique client identifier
MQTT_BROKER    = "broker.mqttdashboard.com"
MQTT_USER      = ""
MQTT_PASSWORD  = ""
MQTT_TOPIC_RECEIVE = "lixeira/comandos"        # Topic for incoming commands
MQTT_TOPIC_SEND    = "lixeira/status"          # Topic for outgoing status


# ---------------------------------------------------------------------------
# ESP32 pin mapping
# ---------------------------------------------------------------------------

PIN_ULTRASONIC_TRIG = 18   # HC-SR04 TRIG pin
PIN_ULTRASONIC_ECHO = 19   # HC-SR04 ECHO pin
PIN_DHT             = 22   # DHT22 data pin
PIN_LID_MOTOR       = 13   # Servo motor PWM pin
PIN_LED             = 23   # Status LED pin


# ---------------------------------------------------------------------------
# Servo / sensor constants
# ---------------------------------------------------------------------------

LID_POS_OPEN   = 90    # PWM duty cycle for open position
LID_POS_CLOSED = 40    # PWM duty cycle for closed position

TRASH_EMPTY_DISTANCE = 50   # Distance (cm) when bin is empty
TRASH_FULL_DISTANCE  = 5    # Distance (cm) when bin is full

HUMIDITY_LIQUID_THRESHOLD = 85.0   # % relative humidity — liquid alert
FILL_ALERT_THRESHOLD      = 80     # % fill level — LED alert


# ---------------------------------------------------------------------------
# Hardware initialisation
# ---------------------------------------------------------------------------

temp_sensor = dht.DHT22(Pin(PIN_DHT))

led = Pin(PIN_LED, Pin.OUT)
led.value(0)   # Ensure LED starts off

lid_motor = PWM(Pin(PIN_LID_MOTOR), freq=50)   # 50 Hz standard servo frequency


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

lid_state: str = "closed"
led_state: str = "off"
mqtt_client: MQTTClient | None = None


# ---------------------------------------------------------------------------
# Sensor helpers
# ---------------------------------------------------------------------------

def read_trash_distance() -> float:
    """Trigger the HC-SR04 and return the measured distance in centimetres.

    Returns -1 on timeout/error.
    """
    trig = Pin(PIN_ULTRASONIC_TRIG, Pin.OUT)
    echo = Pin(PIN_ULTRASONIC_ECHO, Pin.IN)

    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    timeout = 30_000   # µs

    # Wait for echo to go HIGH
    start = time.ticks_us()
    while echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), start) > timeout:
            return -1

    # Measure pulse width
    pulse_start = time.ticks_us()
    while echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), pulse_start) > timeout:
            return -1

    duration = time.ticks_diff(time.ticks_us(), pulse_start)
    distance = (duration * 0.0343) / 2
    return distance


def calculate_fill_percentage(distance: float) -> int:
    """Convert a distance reading into a fill percentage (0–100).

    Returns -1 if *distance* is invalid (-1).
    """
    if distance == -1:
        return -1

    if distance >= TRASH_EMPTY_DISTANCE:
        return 0
    if distance <= TRASH_FULL_DISTANCE:
        return 100

    total_space   = TRASH_EMPTY_DISTANCE - TRASH_FULL_DISTANCE
    current_space = distance - TRASH_FULL_DISTANCE
    percentage    = (1 - current_space / total_space) * 100
    return max(0, min(100, int(percentage)))


def read_temperature_and_humidity() -> tuple[float, float]:
    """Read temperature (°C) and relative humidity (%) from the DHT22.

    Returns ``(-1.0, -1.0)`` on read error.
    """
    try:
        temp_sensor.measure()
        return temp_sensor.temperature(), temp_sensor.humidity()
    except OSError as err:
        print(f"DHT22 read error: {err}")
        return -1.0, -1.0


# ---------------------------------------------------------------------------
# Actuator helpers
# ---------------------------------------------------------------------------

def open_lid() -> None:
    """Move the servo to the open position."""
    global lid_state
    lid_motor.duty(LID_POS_OPEN)
    lid_state = "open"
    print("Trashbin lid: OPEN.")


def close_lid() -> None:
    """Move the servo to the closed position."""
    global lid_state
    lid_motor.duty(LID_POS_CLOSED)
    lid_state = "closed"
    print("Trashbin lid: CLOSED.")


def turn_led_on() -> None:
    """Switch the status LED on (no-op if already on)."""
    global led_state
    if led_state == "off":
        led.value(1)
        led_state = "on"
        print("LED: ON.")


def turn_led_off() -> None:
    """Switch the status LED off (no-op if already off)."""
    global led_state
    if led_state == "on":
        led.value(0)
        led_state = "off"
        print("LED: OFF.")


# ---------------------------------------------------------------------------
# MQTT
# ---------------------------------------------------------------------------

def mqtt_callback(topic: bytes, msg: bytes) -> None:
    """Handle incoming MQTT commands.

    Commands
    --------
    tabre  → open lid
    tfecha → close lid
    lon    → LED on
    loff   → LED off
    """
    command = msg.decode()
    print(f"Received remote command: {topic.decode()} -> {command}")

    handlers = {
        "tabre":  open_lid,
        "tfecha": close_lid,
        "lon":    turn_led_on,
        "loff":   turn_led_off,
    }

    action = handlers.get(command)
    if action:
        action()
    else:
        print(f"Unknown command: '{command}'")


def connect_wifi() -> network.WLAN:
    """Connect to Wi-Fi; reboot on failure."""
    print("Connecting to Wi-Fi", end="")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect("Wokwi-GUEST", "")

    for _ in range(100):
        if wlan.isconnected():
            print(" Connected!")
            return wlan
        print(".", end="")
        time.sleep(0.1)

    print("\nFailed to connect to Wi-Fi. Rebooting...")
    time.sleep(2)
    reset()


def connect_mqtt() -> bool:
    """Connect to the MQTT broker and subscribe to the command topic.

    Returns ``True`` on success, ``False`` on failure.
    """
    global mqtt_client
    print("Connecting to MQTT broker... ", end="")
    try:
        mqtt_client = MQTTClient(
            MQTT_CLIENT_ID, MQTT_BROKER,
            user=MQTT_USER, password=MQTT_PASSWORD,
        )
        mqtt_client.set_callback(mqtt_callback)
        mqtt_client.connect()
        mqtt_client.subscribe(MQTT_TOPIC_RECEIVE)
        print("Connected!")
        return True
    except Exception as err:
        print(f"MQTT connection error: {err}")
        return False


# ---------------------------------------------------------------------------
# Automatic LED logic
# ---------------------------------------------------------------------------

def update_led_alert(fill_percentage: int, humidity: float) -> None:
    """Turn the LED on/off based on fill level and humidity thresholds."""
    bin_nearly_full  = fill_percentage >= FILL_ALERT_THRESHOLD
    liquid_detected  = humidity != -1.0 and humidity > HUMIDITY_LIQUID_THRESHOLD

    if bin_nearly_full or liquid_detected:
        turn_led_on()
        if bin_nearly_full and liquid_detected:
            print("ALERT: Trashbin almost full AND possible liquid detected! LED on.")
        elif bin_nearly_full:
            print("ALERT: Trashbin almost full! LED on.")
        else:
            print("ALERT: Possible liquid detected! LED on.")
    else:
        turn_led_off()
        print("Trashbin not full and no liquid detected. LED off.")


# ---------------------------------------------------------------------------
# Status reporting
# ---------------------------------------------------------------------------

def build_status_message(
    temperature: float,
    humidity: float,
    distance: float,
    fill_percentage: int,
) -> str:
    """Return a formatted status string suitable for MQTT publishing."""
    return (
        "Temp: {:.1f}C, Hum: {:.1f}%, "
        "Dist: {:.1f}cm, Fill: {}%, "
        "Lid: {}, LED: {}".format(
            temperature, humidity, distance, fill_percentage,
            lid_state, led_state,
        )
    )


def print_status(
    distance: float,
    fill_percentage: int,
    temperature: float,
    humidity: float,
) -> None:
    """Print a human-readable status summary to the serial console."""
    print("\n--- Smart Trashbin Status ---")

    if distance != -1:
        print(f"  Trash distance : {distance:.1f} cm")
        print(f"  Fill level     : {fill_percentage}%")
    else:
        print("  Trash distance : read error")
        print("  Fill level     : unavailable")

    print(f"  Temperature    : {temperature:.1f} °C" if temperature != -1.0 else "  Temperature    : read error")
    print(f"  Humidity       : {humidity:.1f}%"      if humidity    != -1.0 else "  Humidity       : read error")
    print(f"  Lid state      : {lid_state}")
    print(f"  LED state      : {led_state}")
    print("-----------------------------")


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------

connect_wifi()

if not connect_mqtt():
    time.sleep(5)
    reset()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

while True:
    try:
        mqtt_client.check_msg()

        # Read sensors
        distance        = read_trash_distance()
        fill_percentage = calculate_fill_percentage(distance)
        temperature, humidity = read_temperature_and_humidity()

        # Console output
        print_status(distance, fill_percentage, temperature, humidity)

        # Automatic LED control
        update_led_alert(fill_percentage, humidity)

        # Publish status over MQTT
        status_message = build_status_message(temperature, humidity, distance, fill_percentage)
        print(f"Publishing to MQTT ({MQTT_TOPIC_SEND}): {status_message}")
        mqtt_client.publish(MQTT_TOPIC_SEND, status_message.encode("utf-8"))

    except OSError as network_err:
        print(f"Network/MQTT error: {network_err}")
        if not connect_mqtt():
            print("MQTT reconnect failed. Rebooting in 5 s...")
            time.sleep(5)
            reset()

    time.sleep(5)
