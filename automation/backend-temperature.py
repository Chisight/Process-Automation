import paho.mqtt.client as mqtt
import socket
import time
from datetime import datetime, timedelta
from lib.config_utils import get_config
import sys
sys.path.append('/usr/lib/python3/dist-packages')
from smbus2 import SMBus

#config
MQTT_BROKER_HOST = get_config('MQTT_BROKER_HOST')
MQTT_BROKER_PORT = int(get_config('MQTT_BROKER_PORT'))
TOPIC_IN_FROM_WEB = get_config('TOPIC_IN_FROM_WEB')
ENVIRONMENT_TOPIC_PREFIX = get_config('ENVIRONMENT_TOPIC_PREFIX')


# Constants
BusNum = 1
AHT20_I2CADDR = 0x38
AHT20_CMD_SOFTRESET = [0xBA]
AHT20_CMD_INITIALIZE = [0xBE, 0x08, 0x00]
AHT20_CMD_MEASURE = [0xAC, 0x33, 0x00]
AHT20_STATUSBIT_BUSY = 7                    # The 7th bit is the Busy indication bit. 1 = Busy, 0 = not.
AHT20_STATUSBIT_CALIBRATED = 3              # The 3rd bit is the CAL (calibration) bit. 1 = Calibrated, 0 = not

# Initialize an AHT20
def init():
    cmd_soft_reset()

    # Check for calibration, if not done then do and wait 10 ms
    if not get_status_calibrated == 1:
        cmd_initialize()
        while not get_status_calibrated() == 1:
            time.sleep(0.01)

def get_normalized_bit(value, bit_index):
    # Return only one bit from value indicated in bit_index
    return (value >> bit_index) & 1

def cmd_soft_reset():
    # Send the command to soft reset
    with SMBus(BusNum) as i2c_bus:
        i2c_bus.write_i2c_block_data(AHT20_I2CADDR, 0x0, AHT20_CMD_SOFTRESET)
    time.sleep(0.04)    # Wait 40 ms after poweron
    return True

def cmd_initialize():
    # Send the command to initialize (calibrate)
    with SMBus(BusNum) as i2c_bus:
        i2c_bus.write_i2c_block_data(AHT20_I2CADDR, 0x0 , AHT20_CMD_INITIALIZE)
    return True

def cmd_measure():
    # Send the command to measure
    with SMBus(BusNum) as i2c_bus:
        i2c_bus.write_i2c_block_data(AHT20_I2CADDR, 0, AHT20_CMD_MEASURE)
    time.sleep(0.08)    # Wait 80 ms after measure
    return True

def get_status():
    # Get the full status byte
    with SMBus(BusNum) as i2c_bus:
        return i2c_bus.read_i2c_block_data(AHT20_I2CADDR, 0x0, 1)[0]
    return True

def get_status_calibrated():
    # Get the calibrated bit
    return get_normalized_bit(get_status(), AHT20_STATUSBIT_CALIBRATED)

def get_status_busy():
    # Get the busy bit
    return get_normalized_bit(get_status(), AHT20_STATUSBIT_BUSY)
        
def get_measure():
    # Get the full measure

    # Command a measure
    cmd_measure()

    # Check if busy bit = 0, otherwise wait 80 ms and retry
    while get_status_busy() == 1:
        time.sleep(0.08) # Wait 80 ns
    
    # Read data and return it
    with SMBus(BusNum) as i2c_bus:
        return i2c_bus.read_i2c_block_data(AHT20_I2CADDR, 0x0, 7)

def get_temperature(unit='C'):
    # Get a measure, select proper bytes, return converted data
    measure = get_measure()
    measure = ((measure[3] & 0xF) << 16) | (measure[4] << 8) | measure[5]
    measure = measure / (pow(2,20))*200-50
    if unit == 'F':
        measure = measure * 9 / 5 + 32
    return measure

def get_humidity():
    # Get a measure, select proper bytes, return converted data
    measure = get_measure()
    measure = (measure[1] << 12) | (measure[2] << 4) | (measure[3] >> 4)
    measure = measure * 100 / pow(2,20)
    return measure

def wait_until_next_minute():
    current_time = datetime.now()
    next_minute = (current_time + timedelta(minutes=1)).replace(second=0, microsecond=0)
    delta = next_minute - current_time
    sleep_seconds = delta.total_seconds()
    #print(f"sleeping {sleep_seconds} seconds.")
    time.sleep(sleep_seconds)

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with result code "+str(rc))

def on_publish(client, userdata, mid):
    print("Message published.")

init()

client = mqtt.Client()
client.on_connect = on_connect
client.on_publish = on_publish

client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)

hostname = socket.gethostname()
topic = f"{TOPIC_IN_FROM_WEB}/{ENVIRONMENT_TOPIC_PREFIX}/{hostname}"

while True:
    wait_until_next_minute()
    temperature = get_temperature("F")
    humidity = get_humidity()
    data = f'{{"time": "{int(time.time())}", "temperature": "{temperature:.2f}°F", "humidity": "{humidity:.2f}%"}}'
    client.publish(topic, data)
    print(f"Published data to topic: {topic}")

