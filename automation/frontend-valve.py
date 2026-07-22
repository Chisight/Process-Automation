import requests
import json
import paho.mqtt.client as mqtt
from lib.config_utils import get_config

# Configuration
MQTT_BROKER_HOST = get_config('MQTT_BROKER_HOST')
MQTT_BROKER_PORT = int(get_config('MQTT_BROKER_PORT'))
TOPIC_IN_FROM_WEB = get_config('TOPIC_IN_FROM_WEB')
TOPIC_OUT_TO_WEB = get_config('TOPIC_OUT_TO_WEB')
VALVE_TOPIC = get_config('VALVE_TOPIC')
VALVE_CONTROL_URL = get_config('VALVE_CONTROL_URL')

VALVE_GPIO = 2

# MQTT Callbacks
def on_mqtt_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with result code " + str(rc))
    client.subscribe(f"{TOPIC_IN_FROM_WEB}/{VALVE_TOPIC}/#")

def on_mqtt_publish(client, userdata, mid):
    print("Message published with mid: " + str(mid))

# Function to control the valve
def control_valve(gpio, value):
    params = {
        "gpio": gpio,
        "value": value
    }
    response = requests.get(VALVE_CONTROL_URL, params=params)
    confirmation = response.text.strip()
    return parse_confirmation(confirmation)

# Function to parse confirmation message and extract GPIO number and state
def parse_confirmation(confirmation):
    if confirmation.startswith("GPIO") and "set to state" in confirmation:
        parts = confirmation.split(" ")
        gpio = parts[1]
        state = parts[-5]  # Extract state from the confirmation message
        if state == "0":
            state = "on"
        elif state == "1":
            state = "off"
        return gpio, state
    else:
        return None, None

def get_last_gpio_state(gpio, url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes

        # Split the response text into lines and iterate over them in reverse order
        lines = response.text.split('\n')[::-1]
        for line in lines:
            #print(f"Handling line: {line}")
            # Check if the line contains "gpio:" at offset 20
            if len(line) > 24 and line[19:24] == "gpio:":
                # Extract GPIO state and pin number
                gpio_info = line[25:].strip().split()
                #print(f"gpio_info: {gpio_info}")
                gpio_pin = gpio_info[0]
                gpio_state = gpio_info[-1]
                confirmation_bit = "off" if gpio_state == "1" else "on"
                # Return the interpreted string
                return gpio_pin, confirmation_bit
            #else:
                #print(f"did not find \"gpio:\": {line[19:24]}")
        return None, None  # Return None if no match is found

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return None, None

# Function to handle MQTT messages
def on_mqtt_message(client, userdata, msg):
    print(f"Received MQTT message with topic: {msg.topic} and payload: {msg.payload}")
    topic_parts = msg.topic.split('/')
    gpio=topic_parts[-1] #last element is the valve gpio number.
    data = json.loads(msg.payload)
    command = data.get("command")
    # Handle the command (turn valve on/off)
    if command == "on":
        # Turn the valve on
        confirmation = control_valve(gpio, 0)
        print("Valve turned ON:", confirmation)
    elif command == "off":
        # Turn the valve off
        confirmation = control_valve(gpio, 1)
        print("Valve turned OFF:", confirmation)
    elif command == "state":
        confirmation = get_last_gpio_state(gpio, VALVE_CONTROL_URL+"log.txt")
        print(f"Got state: gpio {confirmation[0]} state: {confirmation[1]}")
    else:
      return
      
    # Extract GPIO number and state from confirmation
    gpio, state = confirmation
    if gpio is not None and state is not None:
        topic = f"{TOPIC_OUT_TO_WEB}/{VALVE_TOPIC}/{gpio}"  # Construct MQTT topic with GPIO number
        payload = json.dumps({"state": state})  # Construct payload with state
        # Publish confirmation to MQTT topic
        client.publish(topic, payload)

# Main function
def main():
    # Set up MQTT client
    client = mqtt.Client()
    client.on_connect = on_mqtt_connect
    client.on_publish = on_mqtt_publish
    client.on_message = on_mqtt_message
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    client.loop_forever()

if __name__ == "__main__":
    main()

