# Link to the MQTT dashboard (use to view messages):
# https://mqtt-dashboard.com/

import network  # For Wi-Fi connection
import time  # For timing and delays
from machine import Pin, PWM, reset  # For pin control, PWM for the lid motor, and reset
from umqtt.simple import MQTTClient
import dht  # For temperature and humidity sensor

# MQTT server parameters (copied values remain)
MQTT_CLIENT_ID = "FILL"
MQTT_BROKER = "broker.mqttdashboard.com"
MQTT_USER = ""
MQTT_PASSWORD = ""
MQTT_TOPIC_RECEIVE = "lixeira/comandos"  # Topic to receive commands (kept as original)
MQTT_TOPIC_SEND = "lixeira/status"  # Topic to send trashbin status (kept as original)

# ESP32 pin configuration
PIN_ULTRASONIC_TRIG = 18  # TRIG pin of ultrasonic distance sensor
PIN_ULTRASONIC_ECHO = 19  # ECHO pin of ultrasonic distance sensor
PIN_DHT = 22  # DHT22 data pin for temperature and humidity
PIN_LID_MOTOR = 13  # Pin controlling the lid motor (servo)
PIN_LED = 23  # Pin for the LED

# Component initialization
temp_sensor = dht.DHT22(Pin(PIN_DHT))
led = Pin(PIN_LED, Pin.OUT)
led.value(0)  # Ensure LED starts off

# Initialize PWM for the servo motor at 50Hz
lid_motor = PWM(Pin(PIN_LID_MOTOR), freq=50)

# Servo positions for the lid
LID_POS_OPEN = 90
LID_POS_CLOSED = 40

# Initial states
lid_state = "closed"
led_state = "off"

# Calibration distances for the trashbin (in cm)
TRASH_EMPTY_DISTANCE = 50
TRASH_FULL_DISTANCE = 5


# Sensor and actuator functions
def read_trash_distance():
    trig = Pin(PIN_ULTRASONIC_TRIG, Pin.OUT)
    echo = Pin(PIN_ULTRASONIC_ECHO, Pin.IN)

    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    timeout = 30000
    start = time.ticks_us()

    while echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), start) > timeout:
            return -1

    pulse_start = time.ticks_us()

    while echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), pulse_start) > timeout:
            return -1

    duration = time.ticks_diff(time.ticks_us(), pulse_start)

    if duration == -1:
        return -1

    distance = (duration * 0.0343) / 2
    return distance


def calculate_fill_percentage(distance):
    if distance == -1:
        return -1

    if distance >= TRASH_EMPTY_DISTANCE:
        return 0
    elif distance <= TRASH_FULL_DISTANCE:
        return 100
    else:
        total_space = TRASH_EMPTY_DISTANCE - TRASH_FULL_DISTANCE
        current_space = distance - TRASH_FULL_DISTANCE
        percentage = (1 - (current_space / total_space)) * 100
        return max(0, min(100, int(percentage)))


def read_temperature_and_humidity():
    temperature = -1.0
    humidity = -1.0
    try:
        temp_sensor.measure()
        temperature = temp_sensor.temperature()
        humidity = temp_sensor.humidity()
    except OSError as err:
        print(f"DHT22 read error: {err}")
    return temperature, humidity


def open_lid():
    global lid_state
    lid_motor.duty(LID_POS_OPEN)
    lid_state = "open"
    print("Trashbin lid: OPEN.")


def close_lid():
    global lid_state
    lid_motor.duty(LID_POS_CLOSED)
    lid_state = "closed"
    print("Trashbin lid: CLOSED.")


def turn_led_on():
    global led_state
    if led_state == "off":
        led.value(1)
        led_state = "on"
        print("LED: ON.")


def turn_led_off():
    global led_state
    if led_state == "on":
        led.value(0)
        led_state = "off"
        print("LED: OFF.")


# MQTT message callback
def mqtt_callback(topic, msg):
    print(f"Received remote command: {topic.decode()} -> {msg.decode()}")
    command = msg.decode()

    if command == "tabre":
        open_lid()
    elif command == "tfecha":
        close_lid()
    elif command == "lon":
        turn_led_on()
    elif command == "loff":
        turn_led_off()
    else:
        print("Unknown command.")


def connect_wifi():
    print("Connecting to Wi-Fi", end="")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect('Wokwi-GUEST', '')

    max_attempts = 100
    attempts = 0
    while not wlan.isconnected() and attempts < max_attempts:
        print(".", end="")
        time.sleep(0.1)
        attempts += 1

    if wlan.isconnected():
        print(" Connected!")
        return wlan
    else:
        print("\nFailed to connect to Wi-Fi. Rebooting...")
        time.sleep(2)
        reset()
        return None


def connect_mqtt():
    global mqtt_client
    print("Connecting to message broker... ", end="")
    try:
        mqtt_client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, user=MQTT_USER, password=MQTT_PASSWORD)
        mqtt_client.set_callback(mqtt_callback)
        mqtt_client.connect()
        mqtt_client.subscribe(MQTT_TOPIC_RECEIVE)
        print("Connected!")
        return True
    except Exception as mqtt_err:
        print(f"MQTT connection error: {mqtt_err}")
        return False


# Attempt to connect to Wi-Fi
wlan_connection = connect_wifi()

# Attempt to connect to MQTT
if not connect_mqtt():
    time.sleep(5)
    reset()


# Main loop
while True:
    try:
        mqtt_client.check_msg()

        # Read sensors
        distance = read_trash_distance()
        fill_percentage = calculate_fill_percentage(distance)
        temperature, humidity = read_temperature_and_humidity()

        # Print status for debugging
        print("\nSmart Trashbin Status")
        if distance != -1:
            print(f"Trash distance: {distance:.1f} cm")
            print(f"Fill percentage: {fill_percentage}%")
        else:
            print("Trash distance: Read error")
            print("Fill percentage: Unavailable")

        if temperature != -1.0:
            print(f"Temperature: {temperature:.1f} °C")
        else:
            print("Temperature: Read error")

        if humidity != -1.0:
            print(f"Humidity: {humidity:.1f}%")
        else:
            print("Humidity: Read error")

        print(f"Lid state: {lid_state}")
        print(f"LED state: {led_state}")
        print("-------------------------------------")

        # Automatic LED logic
        liquid_detected = False
        if humidity != -1.0 and humidity > 85.0:
            liquid_detected = True

        if fill_percentage >= 80 or liquid_detected:
            turn_led_on()
            if fill_percentage >= 80 and not liquid_detected:
                print("ALERT: Trashbin almost full! LED on.")
            elif liquid_detected and not fill_percentage >= 80:
                print("ALERT: Possible liquid detected! LED on.")
            elif fill_percentage >= 80 and liquid_detected:
                print("ALERT: Trashbin almost full AND possible liquid! LED on.")
        else:
            turn_led_off()
            print("Trashbin not full and no liquid detected. LED off.")

        # Send status via MQTT
        status_message = (
            "Temp: {:.1f}C, Hum: {:.1f}%, "
            "Dist: {:.1f}cm, Fill: {}%, "
            "Lid: {}, LED: {}".format(
                temperature, humidity, distance, fill_percentage, lid_state, led_state
            )
        )
        print(f"Publishing to MQTT ({MQTT_TOPIC_SEND}): {status_message}")
        mqtt_client.publish(MQTT_TOPIC_SEND, status_message.encode('utf-8'))

    except OSError as network_err:
        print(f"Network/MQTT error: {network_err}")
        # Try reconnecting
        if not connect_mqtt():
            print("MQTT reconnect failed. Rebooting in 5s...")
            time.sleep(5)
            reset()

    time.sleep(5)