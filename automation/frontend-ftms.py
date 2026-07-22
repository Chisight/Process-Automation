import sqlite3
import json
import os
import paho.mqtt.client as mqtt
import time
from datetime import datetime, timedelta, timezone
import traceback
from lib.config_utils import get_config
from lib.dictionaryDB import *

# Constants
MQTT_BROKER_HOST = get_config('MQTT_BROKER_HOST')
MQTT_BROKER_PORT = int(get_config('MQTT_BROKER_PORT'))
TOPIC_IN_FROM_WEB = get_config('TOPIC_IN_FROM_WEB')
TOPIC_OUT_TO_WEB = get_config('TOPIC_OUT_TO_WEB')
TREADMILL_TOPIC = get_config('TREADMILL_TOPIC')
ARCHIVE_THRESHOLD = int(get_config('ARCHIVE_THRESHOLD'))
TREADMILL_DB_FILE = get_config('TREADMILL_DB_FILE')
TREADMILL_DB_ARCHIVE = get_config('TREADMILL_DB_ARCHIVE')

# Variable to hold when the last archive was completed
last_archive_time: int = time.time()

last_elapsed_time = None
last_speed = None
last_distance = None

# Function to handle MQTT messages
def on_mqtt_message(client, userdata, msg):
    global last_archive_time
    global last_elapsed_time
    print(f"Received MQTT message with topic: {msg.topic} and payload: {msg.payload}")
    # Extract fields from the payload
    payload = json.loads(msg.payload)
    if payload.get("command") == "state":
        #print("got request for state")
        respond_with_data(client)
    elif "TreadmillData" in payload:
        treadmill_data = payload["TreadmillData"]
        elapsed_time = treadmill_data.get('elapsedTime')
        speed = treadmill_data.get('instantaneousSpeed')
        distance = treadmill_data.get('totalDistance')
        if elapsed_time != last_elapsed_time or  speed != last_speed or distance != last_distance:
            last_elapsed_time = elapsed_time  # Update the last_elapsed_time to the current one
            # Insert the extracted data into the database
            writeDB(TREADMILL_DB_FILE, 'data', treadmill_data, cumulative_fields=['totalDistance', 'totalEnergy', 'elapsedTime'])
            print(f"writeDB: {treadmill_data}")
            respond_with_data(client)

        current_time = time.time()
        if current_time - last_archive_time > 3600:
            #archiveDB(TREADMILL_DB_FILE, 'data', TREADMILL_DB_ARCHIVE, records_to_keep=60)
            last_archive_time = current_time
            respond_with_data(client)

def format_number(value):
    # Convert the value to a string with a maximum of 10 decimal places
    formatted_value = f"{value:.10f}"
    
    # Check if there is a decimal point
    if '.' in formatted_value:
        # Split the string at the decimal point
        integer_part, decimal_part = formatted_value.split('.')
        # Strip trailing zeros from the decimal part
        decimal_part = decimal_part.rstrip('0')
        # Return the formatted number as a float
        return float(f"{integer_part}.{decimal_part}") if decimal_part else float(integer_part)
    else:
        # No decimal point means return as an integer
        return int(formatted_value)

# Function to fetch data from the database and respond on the appropriate topic
def respond_with_data(client):
    try:
        midnight_one_week_ago = int((datetime.now() - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        one_week_ago = int(time.time()) - (7 * 24 * 60 * 60)
        records = readDB(TREADMILL_DB_FILE, 'data', whereClause=f"timeStamp >= {midnight_one_week_ago}", orderBy='id ASC', limit=-1)
        #print(f"Records start at: {records[-1]['timeStamp'] if records else 'No records found'}")

        previous_date = None
        timestamp_list = []
        instantaneous_speed_list = []
        total_distance_list = []
        total_energy_list = []
        elapsed_time_list = []
        
        timestamp_list.append(one_week_ago)
        total_distance_list.append(0)
        total_energy_list.append(0)
        elapsed_time_list.append(0)

        if records:
            previous_day_distance = records[0]['totalDistance']
            previous_day_energy = records[0]['totalEnergy']
            previous_day_elapsed_time = records[0]['elapsedTime']

            #print(f"one_week_ago: {one_week_ago}")
            tzoffset = timedelta(seconds=-time.altzone if time.daylight else -time.timezone) # offset is negative of time.timezone/altzone
            init=0
            for record in records:
                timestamp = record['timeStamp']
                if timestamp >= one_week_ago: # skip up to exactly 7 days back to the second
                    if init==0:
                        init=1
                        #print(f"timestamp: {timestamp}")
                    dt = datetime.utcfromtimestamp(timestamp) + tzoffset # get localtime version of timestamp
                    record_date = dt.date()

                    if previous_date is not None and record_date != previous_date:  # the local date just changed!
                        midnight_dt = datetime(previous_date.year, previous_date.month, previous_date.day) + tzoffset
                        midnight_timestamp = int(midnight_dt.timestamp())

                        if midnight_timestamp < timestamp:  #midnight record append only if there isn't one already
                            temp_midnight_dt = datetime(previous_date.year, previous_date.month, previous_date.day) + timedelta(days=1) + tzoffset
                            while temp_midnight_dt.date() < record_date:
                                timestamp_list.append(int(temp_midnight_dt.timestamp()))
                                total_distance_list.append(0)
                                total_energy_list.append(0)
                                elapsed_time_list.append(0)
                                temp_midnight_dt += timedelta(days=1)
                        #date changed
                        previous_day_distance = record['totalDistance']
                        previous_day_energy = record['totalEnergy']
                        previous_day_elapsed_time = record['elapsedTime']
                        
                    daily_distance = record['totalDistance'] - previous_day_distance
                    daily_energy = record['totalEnergy'] - previous_day_energy
                    daily_elapsed_time = record['elapsedTime'] - previous_day_elapsed_time

                    timestamp_list.append(timestamp)
                    total_distance_list.append(format_number(daily_distance))
                    total_energy_list.append(format_number(daily_energy))
                    elapsed_time_list.append(f"{daily_elapsed_time/60:.1f}")

                    previous_date = record_date

            #append one last record with current timestamp
            timestamp_list.append(int(time.time()))
            total_distance_list.append(format_number(daily_distance))
            total_energy_list.append(format_number(daily_energy))
            elapsed_time_list.append(f"{daily_elapsed_time/60:.1f}")

            # append only one instantaneousSpeed with the most recent speed.
            instantaneous_speed_list.append(format_number(record['instantaneousSpeed']))

        response_payload = json.dumps({
            "instantaneousSpeed": instantaneous_speed_list,
            "time": timestamp_list,
            "totalDistance": total_distance_list,
            "totalEnergy": total_energy_list,
            "elapsedTime": elapsed_time_list,
        })

        out_topic = f"{TOPIC_OUT_TO_WEB}/{TREADMILL_TOPIC}"
        client.publish(out_topic, response_payload)
        # print(f"Published response on topic: {out_topic}, payload: {response_payload}")

    except Exception as e:
        print(f"Error fetching data from database: {e}")
        print("Traceback:")
        traceback.print_exc()

def wait_until_next_hour():
    current_time = datetime.now()
    next_hour = current_time.replace(microsecond=0, second=0, minute=0, hour=(current_time.hour + 1) % 24)
    time.sleep((next_hour - current_time).total_seconds() % 3600)


# Main function
def main():
    # Set up MQTT client
    client = mqtt.Client()
    client.on_message = on_mqtt_message
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    client.subscribe(f"{TOPIC_IN_FROM_WEB}/{TREADMILL_TOPIC}/#")
    client.loop_start()

    # Main loop for hourly calls
    try:
        while True:
            wait_until_next_hour()
            respond_with_data(client)

    except KeyboardInterrupt:
        client.loop_stop()  # Stop the MQTT loop when interrupted
        print("MQTT loop stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    main()

