"""
backend-magichome.py

This script integrates magic_home smart lights with an MQTT broker. It processes 
MQTT commands to control light states or query statuses and communicates with 
devices via TCP.

Key Features:
- Handles MQTT commands for light control and status updates.
- Communicates with magic_home devices using a proprietary protocol.
- Publishes device states to MQTT topics.

To run:
- Place this script in the configured DIRECTORY_TO_WATCH, and Supervisor will 
  automatically start and monitor it.
- Alternatively, it can be run manually with: `python3 backend-magichome.py`.

Major Dependencies:
- `paho.mqtt.client` for MQTT messaging.
- `lib.config_utils` for configuration management.
"""

import json
import socket
import time
import paho.mqtt.client as mqtt
import threading
from lib.config_utils import get_config

# Dictionary to store known bulbs and their types
known_bulbs = {}

def handle_mqtt_message(mqtt_client, userdata, msg):
    """
    Handle MQTT messages received from the broker.

    Args:
        mqtt_client (mqtt.Client): The MQTT client instance.
        userdata (Any): User-defined data of any type passed to callbacks.
        msg (mqtt.MQTTMessage): MQTT message containing topic and payload.
    """
    topic_parts = msg.topic.split('/')
    print(f"Received MQTT message with topic: {msg.topic} and payload: {msg.payload}")
    data = json.loads(msg.payload)
    command = data.get("command")
    host = topic_parts[3]
    response = None

    try:
        # Handle 'state' and 'set_color' commands
        if command == "state":
            response = get_light_status(host)
        else:
            response = set_light_color(host, command)

        if response:
            # Determine light status and publish state
            if response[12:13] == bytes([0xf0]):  # RGB mode
                status_bytes = response[6:9]  # Extract RGB status bytes
            else:
                status_bytes = response[9:10] + response[11:12]  # RGBCW
            status_hex = ''.join('{:02x}'.format(byte) for byte in status_bytes)
            publish_light_state(mqtt_client, host, status_hex)
    except Exception as e:
        print("Error handling message:", e)


def on_mqtt_message(mqtt_client, userdata, msg):
    """
    Spawn a thread to process MQTT messages asynchronously.

    Args:
        mqtt_client (mqtt.Client): The MQTT client instance.
        userdata (Any): User-defined data.
        msg (mqtt.MQTTMessage): MQTT message.
    """
    threading.Thread(target=handle_mqtt_message, args=(mqtt_client, userdata, msg)).start()


def set_light_color(host, color_code):
    """
    Set the light color for a magic_home device.

    Args:
        host (str): IP address of the device.
        color_code (str): Hexadecimal color code.

    Returns:
        bytes: Device response if successful, else None.
    """
    print("Setting light color to", color_code, "for host", host)
    if host not in known_bulbs:
        get_light_status(host)

    if known_bulbs[host] == bytes([0x33]):  # RGB-only device
        print("RGB only")
        hex_bytes = bytes.fromhex('31' + color_code + '00f00f10')
    elif known_bulbs[host] == bytes([0x35]):  # RGBCW device
        if len(color_code) == 6:
            print("RGBCW 6 byte")
            hex_bytes = bytes.fromhex('31' + color_code + '0000f00f10')
        elif len(color_code) == 4:
            print("RGBCW 4 byte")
            hex_bytes = bytes.fromhex('31000000' + color_code + '0f0f10')
        response = send_command(host, hex_bytes)
        hex_bytes = bytes.fromhex('818a8b96')

    response = send_command(host, hex_bytes)
    if response:
        return response
    else:
        print("No response received, getting light status...")
        return get_light_status(host)


def get_light_status(host):
    """
    Get the current status of a magic_home device.

    Args:
        host (str): IP address of the device.

    Returns:
        bytes: Device response containing its status.
    """
    print("Getting light status for host", host)
    hex_bytes = bytes.fromhex('818a8b96')
    response = send_command(host, hex_bytes)
    if host not in known_bulbs:
        known_bulbs[host] = response[1:2]  # Determine device type
        print(f"Added new known bulb: {host} type: {known_bulbs[host]}")
    return response


def send_command(host, command_bytes):
    """
    Send a command to a magic_home device via TCP.

    Args:
        host (str): IP address of the device.
        command_bytes (bytes): Command to send.

    Returns:
        bytes: Response from the device, or None if failed.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)  # Set a timeout of 2 seconds
            s.connect((host, 5577))
            print("Sending command:", command_bytes.hex(), "to host", host)
            s.sendall(command_bytes)
            response = s.recv(1024)
            print("Response from", host, ":", response.hex())
            return response
    except Exception as e:
        print("Error sending command to", host, ":", e)
        return None


def publish_light_state(mqtt_client, host, status_hex):
    """
    Publish the light's current state to MQTT.

    Args:
        mqtt_client (mqtt.Client): The MQTT client instance.
        host (str): IP address of the device.
        status_hex (str): Hexadecimal representation of the light's state.
    """
    print("Publishing light status", status_hex, "for host", host)
    status_topic = f"out/light/magic/{host}"
    status_payload = json.dumps({"state": status_hex})
    mqtt_client.publish(status_topic, status_payload)


def on_mqtt_connect(mqtt_client, userdata, flags, rc):
    """
    Callback for MQTT client connection.

    Args:
        mqtt_client (mqtt.Client): The MQTT client instance.
        userdata (Any): User-defined data.
        flags (dict): Response flags from the broker.
        rc (int): Connection result code.
    """
    print("Connected to MQTT broker with result code " + str(rc))
    mqtt_client.subscribe("in/" + get_config('MAGICHOME_TOPIC') + "/#")


def main():
    """
    Main function to initialize MQTT client and start processing messages.
    """
    global mqtt_client
    mqtt_client = mqtt.Client()
    mqtt_client.on_message = on_mqtt_message
    mqtt_client.on_connect = on_mqtt_connect
    print(f"Connecting to {get_config('MQTT_BROKER_HOST')}:{get_config('MQTT_BROKER_PORT')}")
    mqtt_client.connect(get_config('MQTT_BROKER_HOST'), int(get_config('MQTT_BROKER_PORT')))
    mqtt_client.loop_forever()


if __name__ == "__main__":
    main()

