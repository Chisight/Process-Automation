import asyncio
import subprocess
import time
import json
import paho.mqtt.client as mqtt
from bleak import BleakClient, BleakError
from lib import const as c
from lib.config_utils import get_config
from lib import FTMS as FTMS
from lib.extract_treadmill_data import extract_treadmill_data
import signal

# Configuration constants
MQTT_BROKER_HOST = get_config('MQTT_BROKER_HOST')
MQTT_BROKER_PORT = int(get_config('MQTT_BROKER_PORT'))
MQTT_TOPIC_BODY = get_config('TREADMILL_TOPIC')
TREADMILL_ADDRESS = get_config('TREADMILL_ADDRESS')
TOPIC_IN_FROM_WEB = get_config('TOPIC_IN_FROM_WEB')
NOTIFICATION_TIMEOUT = 3  # seconds

# Global variables
last_notification_time = time.time()
bluetooth_client = None  # Initialize the Bluetooth client variable
last_elapsed_time = None
last_speed = None
last_distance = None
last_minute = None
last_publish_time = 0

# MQTT client setup
mqtt_client = mqtt.Client()

def notification_handler(characteristic_uuid, value):
    global last_notification_time, last_elapsed_time, last_speed, last_distance, last_minute, last_publish_time
    last_notification_time = time.time()  # Update the last notification time

    if str(characteristic_uuid).startswith(c.TreadmillData):
        result = json.loads(extract_treadmill_data(value, units='english'))
        elapsed_time = result["elapsedTime"]
        #print(f"elapsedTime: {elapsed_time}")
        speed = result["instantaneousSpeed"]
        distance = result["totalDistance"]
        current_minute = elapsed_time // 60

        should_publish = False

        if speed != last_speed:
            should_publish = True
        if distance != last_distance:
            should_publish = True
        if current_minute != last_minute:
            should_publish = True
        if speed > 0.0 and time.time() - last_publish_time > 60:
            should_publish = True

        #print(f"elapsedTime: {elapsed_time} last_elapsed_time: {last_elapsed_time}")
        if last_elapsed_time != None and elapsed_time == 0: #handle stop by sending elapsed time from before stop
            result["elapsedTime"]=last_elapsed_time
        last_elapsed_time = elapsed_time

        if should_publish:
            last_speed = speed
            last_distance = distance
            last_minute = current_minute
            last_publish_time = time.time()
            #print(f"write elapsedTime: {result['elapsedTime']}")
            mqtt_client.publish(f"{TOPIC_IN_FROM_WEB}/{MQTT_TOPIC_BODY}", json.dumps({"TreadmillData": result}))

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker")
    client.subscribe(f"{TOPIC_IN_FROM_WEB}/{MQTT_TOPIC_BODY}")  # Subscribe to the input topic

def on_message(client, userdata, msg):
    global last_speed
    payload = json.loads(msg.payload)
    if "command" in payload:
        print(f"Received MQTT command:{payload}")
        if payload["command"] == "start":
            asyncio.run_coroutine_threadsafe(FTMS.start(bluetooth_client), loop)
            time.sleep(3)  # Blocking delay for server start
        elif payload["command"] == "stop":
            asyncio.run_coroutine_threadsafe(FTMS.stop(bluetooth_client), loop)
            time.sleep(1)
        elif payload["command"] == "pause":
            asyncio.run_coroutine_threadsafe(FTMS.pause(bluetooth_client), loop)
        else:
            try:
                speed = float(payload["command"])
                if speed < 5:
                    asyncio.run_coroutine_threadsafe(FTMS.stop(bluetooth_client), loop)
                    time.sleep(1)
                else:
                    if last_speed == 0:
                        asyncio.run_coroutine_threadsafe(FTMS.start(bluetooth_client), loop)
                        time.sleep(3)  # Blocking delay for server start
                    asyncio.run_coroutine_threadsafe(FTMS.set_speed(bluetooth_client, speed / 10, units='english'), loop)
            except:
                pass

async def reset_bluetooth_device():
    """Reset the Bluetooth device using hciconfig."""
    try:
        subprocess.run(['hciconfig', 'hci0', 'reset'], check=True)
        print("Bluetooth device reset successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to reset Bluetooth device: {e}")

async def read_and_subscribe(address):
    global last_notification_time
    while True:
        global bluetooth_client
        bluetooth_client = BleakClient(address)
        try:
            async with bluetooth_client:
                print(f"Connected to {address}")
                await asyncio.sleep(2)
                await bluetooth_client.start_notify(c.TreadmillData, notification_handler)
                await FTMS.request_control(bluetooth_client)
                while True:
                    await asyncio.sleep(1)
                    if time.time() - last_notification_time > NOTIFICATION_TIMEOUT:
                        print("No notifications received for a while. Resetting Bluetooth device...")
                        await reset_bluetooth_device()
                        break
        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            await reset_bluetooth_device()
            await asyncio.sleep(5)

async def main(address):
    # Set up MQTT client
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    mqtt_client.loop_start()  # Start the MQTT loop

    while True:  # Keep the main loop running indefinitely
        await read_and_subscribe(address)

async def cleanup(signal, frame):
    print("Ctrl+C detected. Cleaning up...")
    if bluetooth_client and bluetooth_client.is_connected:
        await bluetooth_client.disconnect()
        print("Bluetooth connection closed.")
    mqtt_client.loop_stop()
    print("MQTT loop stopped.")
    loop.stop()

if __name__ == "__main__":
    # Use the specified Bluetooth address
    device_address = TREADMILL_ADDRESS  # Get the address from config
    loop = asyncio.get_event_loop()

    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, lambda s, f: asyncio.run_coroutine_threadsafe(cleanup(s, f), loop))

    try:
        loop.run_until_complete(main(device_address))
    except KeyboardInterrupt:
        # cleanup is already handled by signal handler.
        pass
    finally:
        loop.close()

