import sqlite3
import socket
import json
import os
import paho.mqtt.client as mqtt
from lib.config_utils import get_config
import atexit
import signal
import sys

# Configuration constants
MQTT_BROKER_HOST = get_config('MQTT_BROKER_HOST')
MQTT_BROKER_PORT = int(get_config('MQTT_BROKER_PORT'))
MQTT_TOPIC_BODY = get_config('WEATHER_TOPIC')
LOCATION = get_config('LOCATION')
TOPIC_IN_FROM_WEB = get_config('TOPIC_IN_FROM_WEB')
TOPIC_OUT_TO_WEB = get_config('TOPIC_OUT_TO_WEB')
SOCKET_PATH = get_config('WEATHER_UPDATE_SOCKET')

def cleanup_socket():
    """Remove the socket file if it exists."""
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

def respond_with_data(client, location):
    """Respond with weather data for a specific location."""
    LOCATION = location
    db_filename = eval(get_config('WEATHER_DB_FILE'))
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    # Fetch the column names
    cursor.execute("PRAGMA table_info(weather_data)")
    column_names = [row[1] for row in cursor.fetchall()]
    if 'id' in column_names:
        column_names.remove('id')  # Remove 'id' if exists

    # Construct the SQL query and retrieve data
    try:
        #print(f"SELECT {', '.join(column_names)} FROM weather_data WHERE location = ?", (location,))
        cursor.execute(f"SELECT {', '.join(column_names)} FROM weather_data WHERE location = ?", (location,))
        data = cursor.fetchall()

        response_data = {column_name: [row[i] for row in data] for i, column_name in enumerate(column_names)}
        response_payload = json.dumps(response_data)

        client.publish(f"{TOPIC_OUT_TO_WEB}/{MQTT_TOPIC_BODY}/{location}", response_payload)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    conn.close()

def handle_update_signal(client):
    """Handle IPC updates using a listening socket that receives the updated location."""
    cleanup_socket()  # Clean up the existing socket file before binding a new one
    
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.bind(SOCKET_PATH)
        sock.listen(1)
        while True:
            connection, _ = sock.accept()
            with connection:
                location = connection.recv(1024).decode()
                if location in LOCATION if isinstance(LOCATION, list) else [LOCATION]:
                    respond_with_data(client, location)

def on_mqtt_message(client, userdata, msg):
    """Handle MQTT messages, retrieving and responding with data for the specified location."""
    location = msg.topic.split('/')[-1]
    payload = json.loads(msg.payload)
    if payload.get("command") == "state" and (location in LOCATION if isinstance(LOCATION, list) else location == LOCATION):
        respond_with_data(client, location)

def main():
    # Register cleanup for socket removal on exit
    atexit.register(cleanup_socket)
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(0))

    # MQTT client setup
    client = mqtt.Client()
    client.on_message = on_mqtt_message
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    
    # Subscribe to topic
    client.subscribe(f"{TOPIC_IN_FROM_WEB}/{MQTT_TOPIC_BODY}/#")
    
    client.loop_start()
    handle_update_signal(client)

if __name__ == "__main__":
    main()

