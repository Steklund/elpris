import requests
from datetime import datetime
import schedule
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import paho.mqtt.client as mqtt
import json

HOURS_FOR_DISCHARGE = 3
UPDATE_AT_MINUTE = ":00"

TRANS_ID = 1

GLOBAL_SOC_VALUE = 50

# Load environment variables from .env file
load_dotenv("mqtt.env")

# Create client instance
client = mqtt.Client()
MQTT_TOPIC = "extapi/control/request"
MQTT_BATTERY_POWER = os.getenv('MQTT_BATTERY_POWER')

# Funktion som körs när ett meddelande mottas från prenumerationen
def on_message(client, userdata, message):
    #print("Meddelande mottaget från ämne:", message.topic)

    if(message.topic == "extapi/control/result"):
        print("Meddelande:", str(message.payload.decode("utf-8")))
    else:
        payload = json.loads(message.payload.decode("utf-8"))
        if "soc" in payload:
            GLOBAL_SOC_VALUE = payload["soc"]["val"]
            print(f"State of Charge (SOC): {GLOBAL_SOC_VALUE}%")



def mqtt_init():

    MQTT_IP = os.getenv('MQTT_IP')
    MQTT_PORT = os.getenv('MQTT_PORT')
    MQTT_USERNAME = os.getenv('MQTT_USERNAME')
    MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')

    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    # Define callback-function for messages 
    client.on_message = on_message

    try:
        client.connect(MQTT_IP, int(MQTT_PORT))
    except Exception as e:
        print("Connection fault:", str(e))
    print("Connected!")

    try:
        client.subscribe("extapi/control/result")
        client.subscribe("extapi/data/esm")
    except Exception as e:
        print("Subscribition fault:", str(e))
    print("Subsribed!")

    # Start loop to listen to messages
    client.loop_start()

# Class to represent elpris, contains price, start-time, end-time and battery behavior.
class Elpris:
    def __init__(self, price, time_start, time_end):
        self.price = price
        self.time_start = time_start
        self.time_end = time_end
        self.behavior = self.determine_behavior()
    
    def determine_behavior(self):
        if self.price < 0:
            return "charge"
        else:
            return "auto"
    
    def __str__(self):
        return f"{self.price} SEK/kWh klockan {self.time_start}-{self.time_end} - {self.behavior}"

# Function called by the schedule to send data to the server.
def send_data():
    priser = get_todays_elpriser()
    if priser:
        formatted_priser = format_elpriser(priser)

        # for debugging 
        #formatted_priser = update_behavior(elpris_debug_list)

        for item in formatted_priser:

            # Debug print
            print(f"Price: {item.price}, Behavior: {item.behavior}")

    today = datetime.now()
    hour_start = today.strftime("%H")
    print(f"Even hour: {hour_start}, as integer {int(hour_start)}")
    item = formatted_priser[int(hour_start)]
    print(f"I found: {item.price}, Behavior: {item.behavior}, from: {item.time_start}, to: {item.time_end}")

    # Access the global variable
    global TRANS_ID
    global GLOBAL_SOC_VALUE

    charge_reference = MQTT_BATTERY_POWER
    discharge_reference = MQTT_BATTERY_POWER

    if(int(GLOBAL_SOC_VALUE) >= 98):
        charge_reference = 0
        print(f"Will ignore charge ({GLOBAL_SOC_VALUE})%")
    elif(int(GLOBAL_SOC_VALUE) <= 16):
        print(f"Will ignore discharge ({GLOBAL_SOC_VALUE})%")
        discharge_reference = 0

    if(item.behavior == "charge"):
        payload = {
            "transId": str(TRANS_ID),  
            "cmd": {
                "name": "charge",  
                "arg": str(charge_reference)
            }
        }
        print("Sent charge")
    elif(item.behavior == "discharge"):
        payload = {
            "transId": str(TRANS_ID),
            "cmd": {
                "name": "discharge",
                "arg": str(discharge_reference)
            }
        }
        print("Sent discharge")
    else:
        payload = {
            "transId": str(TRANS_ID),
            "cmd": {
                "name": "auto"
            }
        }
        print("Sent auto")

    TRANS_ID += 1
    json_payload = json.dumps(payload)
    client.publish(MQTT_TOPIC, json_payload)


    
# Call schedule every hour at 00
schedule.every().hour.at(UPDATE_AT_MINUTE).do(send_data)

def get_todays_elpriser(region="SE2"):
    # Todays date
    today = datetime.now()
    year = today.strftime("%Y")
    month = today.strftime("%m")
    day = today.strftime("%d")
    
    # Build API-url
    url = f"https://www.elprisetjustnu.se/api/v1/prices/{year}/{month}-{day}_{region}.json"
    
    # GET-request to API:et
    response = requests.get(url)
    
    # Check response from request
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Something wrong!: {response.status_code}")
        return None

def format_elpriser(priser):
    formatted_data = []
    for pris in priser:
        time_start = datetime.fromisoformat(pris['time_start']).strftime("%H-%M")
        time_end = datetime.fromisoformat(pris['time_end']).strftime("%H-%M")
        price = pris['SEK_per_kWh']
        elpris = Elpris(price, time_start, time_end)
        formatted_data.append(elpris)

    return update_behavior(formatted_data)

# Function that makes sure the batteries discharge before a charge session
def update_behavior(lst):
    i = 0
    while i < len(lst):
        if lst[i].behavior == "charge":
            j = i - 1
            count = 0
            while j >= 0 and lst[j].behavior != "charge":
                if count < HOURS_FOR_DISCHARGE:  # Limit "discharge" to HOURS_FOR_DISCHARGE before "charge"
                    lst[j].behavior = "discharge"
                    count += 1
                else:
                    break
                j -= 1
            i = max(j + 1, i + 1)  # Set i to the index after the last "discharge" or next index
        else:
            i += 1
    return lst

elpris_debug_list = [
    Elpris(0.17556, "00:00", "01:00"),
    Elpris(-0.1483, "01:00", "02:00"),
    Elpris(-0.10341, "02:00", "03:00"),
    Elpris(0.05715, "03:00", "04:00"),
    Elpris(0.04684, "04:00", "05:00"),
    Elpris(0.02142, "05:00", "06:00"),
    Elpris(0.00825, "06:00", "07:00"),
    Elpris(0.00893, "07:00", "08:00"),
    Elpris(0.00149, "08:00", "09:00"),
    Elpris(0.02302, "09:00", "10:00"),
    Elpris(0.08704, "10:00", "11:00"),
    Elpris(0.17178, "11:00", "12:00"),
    Elpris(-0.28367, "12:00", "13:00"),
    Elpris(-0.37437, "13:00", "14:00"),
    Elpris(-0.42521, "14:00", "15:00"),
    Elpris(0.32844, "15:00", "16:00"),
    Elpris(0.05715, "16:00", "17:00"),
    Elpris(0.00676, "17:00", "18:00"),
    Elpris(0.06986, "18:00", "19:00"),
    Elpris(0.1491, "19:00", "20:00"),
    Elpris(0.18358, "20:00", "21:00"),
    Elpris(0.19984, "21:00", "22:00"),
    Elpris(0.19102, "22:00", "23:00"),
    Elpris(-0.18117, "23:00", "00:00"),
]

if __name__ == "__main__":
        mqtt_init()
        send_data()
        # Run schedule in loop
        while True:
            schedule.run_pending()
            time.sleep(60)  # Wait 60 seconds before checking!

