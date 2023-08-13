from clickhouse_driver import Client
import os
import psycopg2
import os
import yaml
from yaml.loader import SafeLoader
from .ch import load_from_dict
import socket
import time

def setup_postgres():
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST_RW"),
        user=os.getenv("POSTGRES_USERNAME"),
        password=os.getenv("POSTGRES_PASSWORD"),
    database="app"
    )
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weather_station (
    	id serial PRIMARY KEY,
    	station_name VARCHAR ( 255 ) UNIQUE NOT NULL,
        lat float(8) NOT NULL,
        lon float(8) NOT NULL)""")

    cursor.executemany("""INSERT INTO weather_station (station_name, lat, lon) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""", 
                    [
                        ("Oslo", 59.9133, 10.7389),
                        ("Bergen", 60.3894, 5.3300),
                        ("Stavanger", 58.9700, 5.7314),
                        ("Sandnes", 58.8517, 5.7361),
                        ("Trondheim", 63.4297, 10.3933),
                        ("Sandvika", 59.8833, 10.5167),
                        ("Kristiansand", 58.1472, 7.9972),
                        ("Drammen", 59.7378, 10.2050),
                        ("Asker", 59.8331, 10.4392),
                        ("Tønsberg", 59.2981, 10.4236),
                        ("Skien", 59.2081, 9.5528),
                        ("Bodø", 67.2827, 14.3751),
                        ("Ålesund", 62.4740, 6.1582),
                        ("Moss", 59.4592, 10.7008),
                        ("Arendal", 58.4608, 8.7664),
                        ("Lørenskog", 59.8989, 10.9642),
                        ("Tromsø", 69.6828, 18.9428),
                        ("Haugesund", 59.4464, 5.2983),
                        ("Molde", 62.7375, 7.1591),
                        ("Askøy", 60.4667, 5.1500),
                        ("Hamar", 60.7945, 11.0679),
                        ("Oppegård", 59.7925, 10.7903),
                        ("Rygge", 59.3747, 10.7147),
                        ("Steinkjer", 64.0148, 11.4954),
                        ("Randaberg", 59.0017, 5.6153),
                        ("Lommedalen", 59.9500, 10.4667),
                        ("Barbu", 58.4664, 8.7781),
                        ("Tiller", 63.3550, 10.3790),
                        ("Kolbotn", 59.8112, 10.8000),
                        ("Lillestrøm", 59.9500, 11.0833)
                    ])
    conn.commit()


def setup_clickhouse():
    while True:
        try:
            socket.gethostbyname(CLICKHOUSE_HOST)
        except:
            print("Waiting for clickhouse host...")
            time.sleep(60)
        break
    
    CLICKHOUSE_HOST=os.getenv("CLICKHOUSE_HOST")
    CLICKHOUSE_USERNAME=os.getenv("CLICKHOUSE_USERNAME")
    CLICKHOUSE_PASSWORD=os.getenv("CLICKHOUSE_PASSWORD")
    client = Client(CLICKHOUSE_HOST, user=CLICKHOUSE_USERNAME, password=CLICKHOUSE_PASSWORD)

    KAFKA_BOOTSTRAP_HOST = os.getenv("KAFKA_BOOTSTRAP_HOST")

    POSTGRES_HOST=os.getenv("POSTGRES_HOST_R")
    POSTGRES_USERNAME=os.getenv("POSTGRES_USERNAME")
    POSTGRES_PASSWORD=os.getenv("POSTGRES_PASSWORD")

    client.execute(f"""
    CREATE TABLE IF NOT EXISTS WeatherStation_postgres ON CLUSTER `cluster`
    (
        `id` Int64,
        `station_name` String,
        `lat` Float64,
        `lon` Float64
    ) ENGINE = PostgreSQL('{POSTGRES_HOST}', 'app', 'weather_station', '{POSTGRES_USERNAME}', '{POSTGRES_PASSWORD}');
    """)

    with open('./data/clickhouse.yaml') as f:
        data = yaml.load(f, Loader=SafeLoader)

    tables, analytical_tables = load_from_dict(data, f"{KAFKA_BOOTSTRAP_HOST}:9092")

    for t in tables + analytical_tables:
        for query in t.all_create_queries():
            print(f"Executing: {query}")

            client.execute(query)

if __name__ == "__main__":
    print("Running setup-data")
    setup_postgres()
    setup_clickhouse()