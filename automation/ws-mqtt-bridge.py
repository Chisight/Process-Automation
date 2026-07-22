import asyncio
import threading
import websockets
import json
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
from websockets.exceptions import ConnectionClosedError
from lib.config_utils import get_config

TOPIC_IN_FROM_WEB = get_config('TOPIC_IN_FROM_WEB')
TOPIC_OUT_TO_WEB = get_config('TOPIC_OUT_TO_WEB')

async def handle_websocket(websocket, path): # handle traffic "in" from the webpage 
    clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Received message from websocket: {message}")
            data = json.loads(message)
            topic = data.get("topic")
            if topic:
                prefixed_topic = f"{TOPIC_IN_FROM_WEB}/" + topic # traffic "in" from web towards backend modules
                payload = data.get("payload")
                print(f"Publishing topic: {prefixed_topic} with payload: {payload}")
                mqtt_client.publish(prefixed_topic, payload)
    except ConnectionClosedError:
        print("Websocket connection closed unexpectedly.")
    finally:
        clients.remove(websocket)

def on_mqtt_connect(mqtt_client, userdata, flags, rc):
    print("Connected to MQTT broker with result code " + str(rc))
    mqtt_client.subscribe(f"{TOPIC_OUT_TO_WEB}/#") # listen from replies "out" from the backend towards the frontend

def on_mqtt_message(mqtt_client, userdata, msg): # mqtt message from backend "out" towards frontend
    topic = msg.topic
    print(f"Received MQTT message with topic: {msg.topic} and payload: {msg.payload}")
    if topic.startswith(f"{TOPIC_OUT_TO_WEB}/"):
        # Remove the "state/" prefix from the topic
        websocket_topic = topic[len(f"{TOPIC_OUT_TO_WEB}/"):]
        payload = msg.payload.decode("utf-8")
        message = {
            "topic": websocket_topic,
            "payload": payload
        }
        json_message = json.dumps(message)
        print(f"Sending to websocket: {json_message}")
        asyncio.run_coroutine_threadsafe(send_message_to_clients(json_message), loop)

async def send_message_to_clients(json_message):
    for client in clients:
        await client.send(json_message)

async def start_websocket_server():
    await websockets.serve(handle_websocket, "localhost", 8081) # external traffic proxied by Nginx


# Main function to setup MQTT client and start listening
def main():
    global mqtt_client
    global clients
    global loop
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    print(f"connecting to {get_config('MQTT_BROKER_HOST')}:{get_config('MQTT_BROKER_PORT')}")
    mqtt_client.connect(get_config('MQTT_BROKER_HOST'), int(get_config('MQTT_BROKER_PORT')))
    mqtt_client.loop_start()

    clients = set() # set of all frontend client connections
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.get_event_loop().run_until_complete(start_websocket_server())
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()

