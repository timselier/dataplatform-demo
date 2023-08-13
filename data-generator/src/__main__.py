from datetime import date, datetime
import random
from kafka import KafkaProducer
import json
import random
import os
import time
import math


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

KAFKA_BOOTSTRAP_HOST = os.getenv("KAFKA_BOOTSTRAP_HOST")
producer = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_HOST)

WEATHER_STATION_MAX_ID = int(os.getenv("WEATHER_STATION_MAX_ID", 100))
WEATHER_STATION_TOPIC = os.getenv('WEATHER_STATION_TOPIC')
WEATHER_STATION_INTERVAL = float(os.getenv("INTERVAL", "60.0"))

def tick():
    for station_id in range(WEATHER_STATION_MAX_ID):
        random.seed(station_id)
        time_ = time.time()
        msg = {
            "station_id": station_id,
            "measurement_moment": datetime.now(),
            "temperature_ambient": random.uniform(-5, 20) + math.sin(time_/600) * 15,
            "temperature_ground": random.uniform(-5, 20) + math.sin(time_/600) * 15,
            "humidity": random.uniform(0.25, 0.75) + math.sin(time_/800) * 0.25,
            "pressure": random.uniform(990, 1020) + math.sin(time_/1000) * 15,
            "wind_speed": random.uniform(5, 30) + math.sin(time_/600) * 5,
            "precipitation": random.uniform(0, 20) + max(0, math.sin(time_/800) * 5),
            "irradiance": random.uniform(0, 1000) + abs(math.sin(time_/1200) * 5),
        }
        producer.send(
            WEATHER_STATION_TOPIC, 
            json.dumps(msg, default=json_serial).encode(), 
            key=str(station_id).encode())

    print(".")
    
if __name__ == "__main__":
    starttime = time.time()
    while True:
        time.sleep(max(0, WEATHER_STATION_INTERVAL - ((time.time() - starttime) % WEATHER_STATION_INTERVAL)))
        tick()