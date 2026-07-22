import sqlite3
import json
import paho.mqtt.client as mqtt
from lib.config_utils import get_config

# Configuration
MQTT_BROKER_HOST = get_config('MQTT_BROKER_HOST')
MQTT_BROKER_PORT = int(get_config('MQTT_BROKER_PORT'))
TOPIC_IN_FROM_WEB = get_config('TOPIC_IN_FROM_WEB')
NETWORK_TOPIC_PREFIX = get_config('NETWORK_TOPIC_PREFIX')
NETWORK_DATA_FILE = get_config('NETWORK_DATA_FILE')
NETWORK_DATA_ARCHIVE = get_config('NETWORK_DATA_ARCHIVE')

# Functions for database operations
def create_or_connect_db(db_filename, interface):
    """Connect to the database and ensure the table exists with a primary key."""
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    table_name = f"interface_{interface}"
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY,
            timestamp INTEGER,
            rx_bytes INTEGER,
            tx_bytes INTEGER,
            rx_packets INTEGER,
            tx_packets INTEGER,
            rst_packets INTEGER
        )
    ''')
    conn.commit()
    return conn, table_name

def insert_into_db(conn, table_name, data):
    """Insert data into the database."""
    cursor = conn.cursor()
    cursor.execute(f'''
        INSERT INTO {table_name} (
            timestamp, rx_bytes, tx_bytes, rx_packets, tx_packets, rst_packets
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        data["timestamp"], data["rx_bytes"], data["tx_bytes"],
        data["rx_packets"], data["tx_packets"], data["rst_packets"]
    ))
    conn.commit()

# MQTT Handlers
def on_connect(client, userdata, flags, rc):
    """Subscribe to the topic upon connecting to the MQTT broker."""
    print(f"Connected to MQTT broker with result code {rc}")
    client.subscribe(f"{TOPIC_IN_FROM_WEB}/{NETWORK_TOPIC_PREFIX}/#")

def create_or_connect_state_tracking_db(conn):
    """Ensure the state_tracking table exists."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS state_tracking (
            interface TEXT PRIMARY KEY,
            offset_rst_packets INTEGER DEFAULT 0,
            last_cumulative_rst_packets INTEGER DEFAULT 0
        )
    ''')
    conn.commit()

def load_state(conn, interface):
    """Load the offset and last cumulative value for an interface."""
    cursor = conn.cursor()
    cursor.execute("SELECT offset_rst_packets, last_cumulative_rst_packets FROM state_tracking WHERE interface = ?", (interface,))
    row = cursor.fetchone()
    if row:
        return {"offset": row[0], "last_cumulative": row[1]}
    else:
        # Initialize state if not found
        cursor.execute("INSERT INTO state_tracking (interface) VALUES (?)", (interface,))
        conn.commit()
        return {"offset": 0, "last_cumulative": 0}

def save_state(conn, interface, offset, last_cumulative):
    """Save the offset and last cumulative value for an interface."""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE state_tracking
        SET offset_rst_packets = ?, last_cumulative_rst_packets = ?
        WHERE interface = ?
    ''', (offset, last_cumulative, interface))
    conn.commit()

def on_message(client, userdata, msg):
    """Process incoming messages and handle counter resets."""
    try:
        topic_parts = msg.topic.split('/')
        location, interface = topic_parts[2], topic_parts[3]
        db_filename = NETWORK_DATA_FILE.format(location=location)
        conn = sqlite3.connect(db_filename)
        table_name = f"interface_{interface}"

        # Ensure state tracking table exists
        create_or_connect_state_tracking_db(conn)

        # Parse the payload
        payload = json.loads(msg.payload)

        # Skip messages with "command" field
        if "command" in payload:
            print(f"Ignoring command message: {payload}")
            return

        # Load the current state
        state = load_state(conn, interface)
        offset = state["offset"]
        last_cumulative = state["last_cumulative"]

        # Process RST_Packets
        new_rst_packets = payload["RST_Packets"]

        if new_rst_packets < (last_cumulative - offset):
            # Reset detected; increment the offset by the last cumulative value
            offset = last_cumulative
            print(f"Reset detected. New offset: {offset}")

        # Calculate the cumulative value
        cumulative_rst_packets = new_rst_packets + offset

        # Save the cumulative value to the database
        data = {
            "timestamp": payload["timestamp"],
            "rx_bytes": payload["RX_Bytes"],
            "tx_bytes": payload["TX_Bytes"],
            "rx_packets": payload["RX_Packets"],
            "tx_packets": payload["TX_Packets"],
            "rst_packets": cumulative_rst_packets
        }
        insert_into_db(conn, table_name, data)

        # Update state with the correct offset and cumulative value
        save_state(conn, interface, offset, cumulative_rst_packets)

        conn.close()
    except Exception as e:
        print(f"Error processing message: {e}")


# Main function
def main():
    """Main entry point for the program."""
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    client.loop_forever()

if __name__ == "__main__":
    main()

