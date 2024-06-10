import requests
from datetime import datetime
import schedule
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

MQTT_IP = os.getenv('MQTT_IP')
MQTT_USERNAME = os.getenv('MQTT_USERNAME')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')

HOURS_FOR_DISCHARGE = 3
UPDATE_AT_MINUTE = ":00"

# Class to represent elpris, contains price, start-time, end-time and battery behavior.
class Elpris:
    def __init__(self, price, time_start, time_end):
        self.price = price
        self.time_start = time_start
        self.time_end = time_end
        self.behavior = self.determine_behavior()
    
    def determine_behavior(self):
        if self.price < 0:
            return "Charging"
        else:
            return "Auto"
    
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

    #
    # HERE I WILL NEED TO ACCESS A FEW PIECES FOR MQTT COMMUNICATION! IP, USERNAME, PASSWORD.
    #

    
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
        if lst[i].behavior == "Charging":
            j = i - 1
            count = 0
            while j >= 0 and lst[j].behavior != "Charging":
                if count < HOURS_FOR_DISCHARGE:  # Limit "Discharge" to HOURS_FOR_DISCHARGE before "Charging"
                    lst[j].behavior = "Discharge"
                    count += 1
                else:
                    break
                j -= 1
            i = max(j + 1, i + 1)  # Set i to the index after the last "Discharge" or next index
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
        send_data()
        # Run schedule in loop
        while True:
            schedule.run_pending()
            time.sleep(60)  # Wait 60 seconds before checking!

