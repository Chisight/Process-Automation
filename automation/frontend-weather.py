import requests
import xml.etree.ElementTree as ET
import sqlite3
import socket
import os
import time
from datetime import datetime
from lib.config_utils import get_config

# Configuration constants - We use get_config to get either single or multiple values.
LOCATIONS = get_config('LOCATION')
#print(f"backend-weather LOCATIONS is {LOCATIONS}")
DATA_URLS = get_config('WEATHER_DATA_URL')
#print(f"backend-weather DATA_URLS is {DATA_URLS}")
SOCKET_PATH = get_config('WEATHER_UPDATE_SOCKET')
#print(f"backend-weather SOCKET_PATH is {SOCKET_PATH}")

# Ensure LOCATIONS and DATA_URLS are lists to handle multiple values.
if isinstance(LOCATIONS, str):
    LOCATIONS = [LOCATIONS]
if isinstance(DATA_URLS, str):
    DATA_URLS = [DATA_URLS]

# Mapping of XML paths to database field names for weather attributes.
field_mapping = [
    {'xml_path': ".//data//parameters//temperature[@type='hourly']/value", 'db_field': 'temperature'},
    {'xml_path': ".//data//parameters//temperature[@type='heat index']/value", 'db_field': 'apparentTemperature'},
    {'xml_path': ".//data//parameters//temperature[@type='wind chill']/value", 'db_field': 'apparentTemperature'},
    {'xml_path': ".//data//parameters//humidity[@type='relative']/value", 'db_field': 'humidity'},
    {'xml_path': ".//data//parameters//probability-of-precipitation/value", 'db_field': 'precipitation'},
    {'xml_path': ".//data//parameters//cloud-amount/value", 'db_field': 'cloudcover'},
    {'xml_path': ".//wind-speed[@type='sustained']/value", 'db_field': 'wind'},
    {'xml_path': ".//wind-speed[@type='gust']/value", 'db_field': 'gusts'},
]

# Namespace for XML elements
namespace = {}

# Function to fetch XML data from URL with retry mechanism.
def fetch_xml_data_with_retry(xml_url, retries=3, backoff_factor=2):
    for attempt in range(retries):
        response = requests.get(xml_url)
        if response.status_code == 200:
            return response.content
        else:
            print(f"Attempt {attempt+1}: Failed to fetch XML data: {response.status_code} - {datetime.now()}")
            time.sleep(backoff_factor ** attempt)
    return None

# Function to convert datetime string from XML to UNIX timestamp.
def datetime_to_unixtime(datetime_str):
    dt_obj = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))  # Assuming UTC timezone
    return int(dt_obj.timestamp())

# Function to parse XML and insert relevant data into the SQLite database.
def parse_xml_and_insert_data(conn, xml_data, location):
    root = ET.fromstring(xml_data)
    cursor = conn.cursor()

    # Start a transaction
    cursor.execute("BEGIN TRANSACTION")
    try:
        # Delete old records
        cursor.execute("DELETE FROM weather_data")
        # Locate time-layout elements in the XML.
        time_layouts = root.findall(".//time-layout", namespace)
        for time_layout in time_layouts:
            # Extract time layout key and start-valid-time elements
            layout_key = time_layout.find("layout-key", namespace).text
            start_valid_times = [time.text for time in time_layout.findall("start-valid-time", namespace)]

            # Dictionary to accumulate values for each timestamp.
            combined_values = {field['db_field']: [] for field in field_mapping}
            
            # Populate combined_values with extracted data from XML based on field mappings.
            for mapping in field_mapping:
                values = root.findall(mapping['xml_path'], namespace)
                for i, value in enumerate(values):
                    combined_values[mapping['db_field']].append(value.text if value.text is not None else 'null')

            # Insert the combined data record for each timestamp into the database.
            for i, time_value in enumerate(start_valid_times):
                values_to_insert = [datetime_to_unixtime(time_value), location]
                values_to_insert.extend([combined_values[field['db_field']][i] for field in field_mapping])
                placeholders = ', '.join(['?' for _ in values_to_insert])
                cursor.execute(f"INSERT INTO weather_data (time, location, {', '.join([field['db_field'] for field in field_mapping])}) VALUES ({placeholders})", values_to_insert)

        # Commit the transaction if everything is successful.
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error while parsing XML and inserting data: {e}")

# Function to notify the frontend responder through a UNIX socket.
def notify_responder(location):
    if not os.path.exists(SOCKET_PATH):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(SOCKET_PATH)
        sock.listen(1)
        sock.close()

    # Convert location to bytes before sending
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(SOCKET_PATH)
        sock.sendall(location.encode('utf-8'))  # Encode location to bytes

# Function to create or connect to SQLite database file.
# Function to create SQLite table
def create_or_connect_db(db_filename):
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    # Initialize columns with the primary keys and base columns
    columns = ['id INTEGER PRIMARY KEY', 'time TIMESTAMP', 'location TEXT']
    
    # Use a set to avoid duplicates
    unique_fields = {mapping['db_field'] for mapping in field_mapping}
    
    # Extend the columns list with unique field names
    columns.extend([f"{field} TEXT" for field in unique_fields])

    # Create the SQL statement
    sql = f"CREATE TABLE IF NOT EXISTS weather_data ({', '.join(columns)})"
    cursor.execute(sql)

    conn.commit()
    return conn

# Function to wait until the start of the next hour.
def wait_until_next_hour():
    current_time = datetime.now()
    next_hour = current_time.replace(microsecond=0, second=0, minute=0, hour=(current_time.hour + 1) % 24)
    time.sleep((next_hour - current_time).total_seconds() % 3600)

# Main function that iterates over LOCATIONS and DATA_URLS.
def main():
    while True:
        for location, data_url in zip(LOCATIONS, DATA_URLS): #zip relates relative values
            # Dynamically update DB_FILE for each LOCATION.
            LOCATION=location
            db_file = eval(get_config('WEATHER_DB_FILE'))
            dbconn = create_or_connect_db(db_file)
            # Loop to fetch XML data, process it, and notify responder on update.
            xml_data = fetch_xml_data_with_retry(data_url)
            if xml_data:
                parse_xml_and_insert_data(dbconn, xml_data, location)
                notify_responder(location)
        wait_until_next_hour()

if __name__ == "__main__":
    main()

