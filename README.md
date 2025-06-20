# Smart Trash Bin Project - PUCPR

## Project Overview

### Urban Waste Problem  
Urban solid waste management is an ever-growing challenge for cities, impacting both the environment and public finances. Current collection methods rely on fixed routes and schedules, regardless of trash bin fill levels, resulting in significant inefficiencies:

- **Overflowing Bins:** In high-traffic areas, bins fill up before scheduled collection, leading to litter, bad smells, pest proliferation, visual pollution, public dissatisfaction, and health risks.
- **Inefficient Collections:** Empty or partially filled bins are sometimes collected, wasting resources such as fuel, staff time, and vehicle wear.

**The Need:**  
A real-time trash bin monitoring system is crucial to optimize collection routes, reduce operational costs, improve urban cleanliness, and promote more efficient and sustainable waste management. Smart bins enable proactive, data-driven collection, focusing efforts where and when they are needed most.

---

## Smart Trash Bin with Monitoring and Notification

This project develops a smart trash bin that continuously monitors its fill level and reports this information to a cloud service, which can then alert collection teams or users. The core controller is the ESP32 due to its Wi-Fi and Bluetooth connectivity.

### Chosen Sensors and Actuators

#### Sensors:
- **Ultrasonic Sensor (HC-SR04):** Measures the distance from the lid to the trash, determining the fill level. Mounted inside the lid.
- **Temperature & Humidity Sensor (DHT22):** Measures air temperature and humidity inside the bin. While not a direct liquid detector, high humidity may suggest the presence of liquids (such as leachate).

#### Actuators:
- **Servo Motor:** Controls the opening and closing of the bin lid, which can be operated remotely.
- **LED:** Serves as an alert indicator. The LED lights up if the bin is full or high humidity is detected, alerting nearby collection staff.

---

## ESP32 Features

- **Sensor Reading:**  
  - Collects data from the ultrasonic sensor (trash level) and DHT22 (temperature & humidity).
- **Data Processing:**  
  - Converts readings into a percentage fill level.
  - Sets thresholds for fill and humidity to trigger alerts or actuator responses.
- **Actuator Control:**  
  - Operates the servo to open/close the lid based on fill level or object proximity.
  - Activates the LED indicator for full bin or high humidity.
- **Wi-Fi Connectivity:**  
  - Connects to local Wi-Fi to communicate with the cloud.
- **Cloud Communication (MQTT):**  
  - Publishes sensor data (`distance`, `fill_percentage`, `temperature`, `humidity`, `lid_status`, `alarm_status`) to the `lixeira/status` MQTT topic.
  - Subscribes to the `lixeira/comandos` MQTT topic for commands (e.g., open/close lid, turn alarm on/off).

---

## Device Communication & MQTT Setup

The client device (smartphone or tablet) uses an MQTT client app to communicate with the ESP32 via the cloud.

### MQTT Configuration

- **Connection:**  
  - The device connects to a public MQTT broker (e.g., `broker.mqttdashboard.com`).
- **Topic Subscription:**  
  - `lixeira/status`: Receives bin status data.
  - `lixeira/comandos`: Sends commands to the bin (e.g., "tabre" to open, "tfecha" to close).
- **Publishing Commands:**  
  - The device can send messages such as "tabre", "tfecha", "lon", "loff" for remote operation.

#### Data Structure

- **Sent by ESP32:**
  - `distancia`: Numeric value in centimeters (distance).
  - `preenchimento`: Numeric percentage (fill level, 0-100).
  - `temperatura`: Temperature in Celsius.
  - `umidade_ar`: Relative humidity percentage.
  - `tampa`: Lid status ("aberta" or "fechada").
  - `alarme`: Alarm status ("ligado" or "desligado").

- **Commands Received by ESP32:**
  - "tabre", "tfecha", "lon", "loff"

---

## Project Presentation on Wokwi

You can view and interact with the project simulation on Wokwi:

**[Wokwi Project Link](https://wokwi.com/projects/433376981031837697)**

---

## Code Explanation

The code for this project is available in the repository. It manages sensor readings, data processing, actuator control, and MQTT communication as described above.

---

## Conclusions

This project offers an efficient solution to optimize urban waste management. By integrating an ultrasonic sensor for fill level and a DHT22 sensor for environmental monitoring, along with an LED and servo motor, the system enables interactive monitoring and control of a smart trash bin.

The ESP32 is ideal as the central controller due to its Wi-Fi capabilities, enabling real-time communication with the MQTT broker in the cloud. Communication with a mobile device demonstrates the feasibility of notifying collection teams and managers about bin status and receiving remote commands, allowing for smarter and more responsive collection routes.

**Direct benefits include:**
- Reduced operational costs (by avoiding unnecessary collections)
- Improved urban cleanliness (preventing overflowing bins)
- Positive environmental impact through optimized logistics

This system is a step toward smarter, more sustainable cities, where waste management is proactive and data-driven.

---

## Future Improvements

- **Map Integration:** Develop a web or mobile interface with map visualization for all bins.
- **Historical Data Analysis:** Implement analytics to predict fill patterns and further optimize routes.
- **Solar Power:** Add solar charging for self-sustaining operation in areas without easy electrical access.
- **Advanced Liquid Detection:** Add a dedicated liquid or soil moisture sensor for more precise leachate detection.
- **GPS Module:** Send bin location data to the client.

---

