import sqlite3
import json
import os
import paho.mqtt.client as mqtt
import time
from datetime import datetime
import traceback
from lib.config_utils import get_config
from lib.dictionaryDB import *

# Constants
MQTT_BROKER_HOST = get_config('MQTT_BROKER_HOST')
MQTT_BROKER_PORT = int(get_config('MQTT_BROKER_PORT'))
TOPIC_IN_FROM_WEB = get_config('TOPIC_IN_FROM_WEB')
TOPIC_OUT_TO_WEB = get_config('TOPIC_OUT_TO_WEB')
ENVIRONMENT_TOPIC_PREFIX = get_config('ENVIRONMENT_TOPIC_PREFIX')
ARCHIVE_THRESHOLD = int(get_config('ARCHIVE_THRESHOLD'))
ENVIRONMENT_DATA_FILE = get_config('ENVIRONMENT_DATA_FILE')
ENVIRONMENT_DATA_ARCHIVE = get_config('ENVIRONMENT_DATA_ARCHIVE')

# Variable to hold when the last archive was completed
last_archive_time: int = time.time()

# Function to handle MQTT messages
def on_mqtt_message(client, userdata, msg):
    global last_archive_time
    print(f"Received MQTT message with topic: {msg.topic} and payload: {msg.payload}")
    # Extract the last element of the topic as the location
    topic_parts = msg.topic.split('/')
    if len(topic_parts) < 3:
        print(f"Invalid topic format. Expected format: '{TOPIC_IN_FROM_WEB}/{ENVIRONMENT_TOPIC_PREFIX}/<location>'")
        return

    location = topic_parts[-1]
    # Extract fields from the payload
    payload = json.loads(msg.payload)
    if "command" in payload and payload["command"] == "state":
        # Respond with data from the database
        respond_with_data(client, location)
    else:
        # Insert data into the database
        fields = payload.keys()
        writeDB(eval(ENVIRONMENT_DATA_FILE), 'mqtt_data', payload, timestamp_field='time')
        # Move old data to archive if necessary
        current_time = time.time()
        if current_time - last_archive_time > 3600:
            archiveDB(eval(ENVIRONMENT_DATA_FILE), 'mqtt_data', eval(ENVIRONMENT_DATA_ARCHIVE), records_to_keep=60)
            last_archive_time = current_time
        respond_with_data(client, location)

# Function to fetch data from the database and respond on the appropriate topic
def respond_with_data(client, location):
    # Fetch the most recent records from the database
    try:
        records = readDB(eval(ENVIRONMENT_DATA_FILE), 'mqtt_data', limit=60, orderBy='id DESC')
        # Check if any records were returned
        if not records:
            print("No records found.")
            return

        # Initialize lists to hold the aggregated data
        time_list = []
        temperature_list = []
        humidity_list = []
        location_list = []

        # Populate the lists with data from each record
        for record in reversed(records):  # This uses the reversed() function
            time_list.append(record['time'])
            temperature_list.append(record['temperature'])
            humidity_list.append(record['humidity'])

        # Create a response payload with lists
        location_list.append(location)  # Add location only once
        response_payload = json.dumps({
            "time": time_list,
            "temperature": temperature_list,
            "humidity": humidity_list,
            "location": location_list
        })

        out_topic = f"{TOPIC_OUT_TO_WEB}/{ENVIRONMENT_TOPIC_PREFIX}/{location}"
        client.publish(out_topic, response_payload)
        print(f"Published response on topic: {out_topic}, payload: {response_payload}")
    except Exception as e:
        print(f"Error fetching data from database: {e}")
        print("Traceback:")
        traceback.print_exc()  # This will print the full traceback


# Main function
def main():
    # Set up MQTT client
    client = mqtt.Client()
    client.on_message = on_mqtt_message
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    client.subscribe(f"{TOPIC_IN_FROM_WEB}/{ENVIRONMENT_TOPIC_PREFIX}/#")
    client.loop_forever()

if __name__ == "__main__":
    main()

