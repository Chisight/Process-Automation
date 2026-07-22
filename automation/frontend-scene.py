import paho.mqtt.client as mqtt
import sqlite3
import time
import threading
from lib.config_utils import get_config

# Constants
MQTT_BROKER_HOST = get_config('MQTT_BROKER_HOST')
MQTT_BROKER_PORT = int(get_config('MQTT_BROKER_PORT'))
SCENE_DB_FILE = get_config('SCENE_DB_FILE')

# Dictionary to store connections to different servers
server_connections = {}

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    # Subscribe to the topic
    client.subscribe("in/sequence/#")

def on_message(client, userdata, msg):
    # Extract the sequence and command data from the MQTT message
    sequence_name = msg.topic.split("/")[-1]
    command_data = msg.payload.decode("utf-8")
    # Look up in the database
    commands = get_commands_from_database(sequence_name, command_data)
    if commands:
        # Execute commands
        i = 0
        while i < len(commands):
            command_id, sequence_name, command_data, topic, cmd, sequence_order, delay, server, next_step = commands[i]
            # Publish MQTT message
            if server == MQTT_BROKER_HOST:
                client.publish(topic, cmd)
                print("Published to topic:", topic, "with command:", cmd)
                # Delay if necessary
                time.sleep(delay / 1000)  # Convert delay to seconds
            else:
                # Use existing connection or create new one
                if server not in server_connections:
                    server_connections[server] = {"client": mqtt.Client()}
                    server_connections[server]["client"].connect_async(server, MQTT_BROKER_PORT, 60)
                    server_connections[server]["client"].loop_start()
                # Wait until the connection is established
                while not server_connections[server]["client"].is_connected():
                    time.sleep(0.1)
                    # print(".", end="", flush=True)  # Print dot without newline and flush buffer
                print()  # Print newline after all dots
                # Publish MQTT message
                server_connections[server]["client"].publish(topic, cmd)
                print("Published to server:", server, "topic:", topic, "with command:", cmd)
            # Delay if necessary
            time.sleep(delay / 1000)  # Convert delay to seconds
            # Check for next step
            if next_step:
                # Find the index of the next step command
                next_step_index = None
                for j in range(len(commands)):
                    if commands[j][6] == next_step:  # Assuming sequence_order is at index 6
                        next_step_index = j
                        break
                if next_step_index is not None:
                    i = next_step_index
                else:
                    i += 1  # Move to the next command if next step not found
            else:
                i += 1
        # Close all connections except MQTT_BROKER_HOST
        server_keys = list(server_connections.keys())  # Create a list of keys to iterate over
        for server in server_keys:
            server_connections[server]["client"].disconnect()
            del server_connections[server]  # Remove entry from server_connections

def get_commands_from_database(sequence_name, command_data):
    # Connect to the database
    conn = sqlite3.connect(SCENE_DB_FILE)
    c = conn.cursor()

    # Query the database
    c.execute("SELECT * FROM mqtt_commands WHERE sequence_name=? AND command_data=? ORDER BY sequence_order", (sequence_name, command_data))
    commands = c.fetchall()

    # Close the database connection
    conn.close()

    return commands

def main():
    # Create an MQTT client
    client = mqtt.Client()
    # Set up callbacks
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to MQTT broker
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)

    # Start the MQTT client loop
    client.loop_forever()

if __name__ == "__main__":
    main()

