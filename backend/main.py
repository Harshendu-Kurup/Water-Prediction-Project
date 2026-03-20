import os
from dotenv import load_dotenv
import requests
import psycopg2
import time
import random
import threading
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from backend.ml_model.predict import predict
import json

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Added CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# ==============================
# DATABASE CONNECTION
# ==============================


def get_connection():
    """
    Get database connection using environment variables.
    Falls back to local development settings if env vars not set.
    """
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        database=os.environ.get("DB_NAME", "iot-test"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        sslmode=os.environ.get("DB_SSLMODE", "prefer")  # Use "require" for Aiven
    )


# ==============================
# CREATE TABLES
# ==============================
def create_tables():

    conn = get_connection()
    cur = conn.cursor()

    # Sensor data table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
    id SERIAL PRIMARY KEY,
    node_id VARCHAR(50),
    field1 FLOAT,
    field2 FLOAT,
    created_at TIMESTAMP
   )
     """)
    # Tank parameters table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tank_sensorparameters (
        id SERIAL PRIMARY KEY,
        node_id VARCHAR(50),
        tank_height_cm FLOAT,
        tank_length_cm FLOAT,
        tank_width_cm FLOAT,
        lat FLOAT,
        long FLOAT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    input_data JSON,
    prediction TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Force fix column type (in case already exists wrong)
    cur.execute("""
    ALTER TABLE predictions
    ALTER COLUMN prediction TYPE TEXT USING prediction::TEXT;
    """)

    conn.commit()
    cur.close()
    conn.close()


# ==============================
# THINGSPEAK CONFIG
# ==============================
REAL_DATA_WITH_CURRENT_TIME = False
TEST_MODE = True

# Node id of sensor
NODE_ID = "NODE_001"

# ThingSpeak API
url = "https://api.thingspeak.com/channels/3290444/feeds.json?api_key=AWP8F08WA7SLO5EQ&results=-1"

last_created_at = None


# ==============================
# GENERATE TEST DATA
# ==============================
def generate_test_data():

    import random

    # Choose category randomly
    category = random.choice(["low", "medium", "high"])

    if category == "low":
        distance = random.uniform(5, 20)      # → overflow
    elif category == "medium":
        distance = random.uniform(30, 60)    # → empty
    else:
        distance = random.uniform(80, 110)   # → filling

    temperature = random.uniform(18, 30)

    return {
        "distance": round(distance, 1),
        "temperature": round(temperature, 1),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ==============================
# SENSOR DATA COLLECTOR
# ==============================
def sensor_collector():

    global last_created_at

    print("Distance & Temperature Data Collector Started")

    while True:

        try:

            if TEST_MODE:

                test_data = generate_test_data()

                distance = test_data["distance"]
                temperature = test_data["temperature"]
                created_at = test_data["created_at"]

            else:

                response = requests.get(url)
                data = response.json()

                feed = data["feeds"][0]

                distance = float(feed["field1"])
                temperature = float(feed["field2"])
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print("NEW DATA:", distance, temperature, created_at)

            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
            INSERT INTO sensor_data
            (node_id, field1, field2, created_at)
            VALUES (%s,%s,%s,%s)
            """,
                        (NODE_ID, distance, temperature, created_at))

            conn.commit()

            cur.close()
            conn.close()

            print("Sensor data inserted")

        except Exception as e:

            print("Error:", e)

        time.sleep(20)


# ==============================
# REQUEST MODEL
# ==============================
class TankParameters(BaseModel):

    node_id: str
    tank_height_cm: float
    tank_length_cm: float
    tank_width_cm: float
    lat: float
    long: float


# ==============================
# POST API
# ==============================
@app.post("/tank-parameters")
def create_tank_parameters(data: TankParameters):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO tank_sensorparameters
    (node_id, tank_height_cm, tank_length_cm, tank_width_cm, lat, long)
    VALUES (%s,%s,%s,%s,%s,%s)
    RETURNING id
    """,
                (
                    data.node_id,
                    data.tank_height_cm,
                    data.tank_length_cm,
                    data.tank_width_cm,
                    data.lat,
                    data.long
                ))

    new_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return {
        "message": "Tank parameters inserted successfully",
        "id": new_id
    }


# ==============================
# GET API
# ==============================
@app.get("/tank-parameters")
def get_tank_parameters():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM tank_sensorparameters")

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for row in rows:
        result.append({
            "id": row[0],
            "node_id": row[1],
            "tank_height_cm": row[2],
            "tank_length_cm": row[3],
            "tank_width_cm": row[4],
            "lat": row[5],
            "long": row[6]
        })

    return result


# ==============================
# GET SENSOR DATA API
# ==============================
@app.get("/sensor-data")
def get_sensor_data(node_id: str = None):

    conn = get_connection()
    cur = conn.cursor()

    if node_id:
        cur.execute("""
        SELECT id,node_id,field1,field2,created_at
        FROM sensor_data
        WHERE node_id = %s
        ORDER BY created_at DESC
        """, (node_id,))
    else:
        cur.execute("""
        SELECT id,node_id,field1,field2,created_at
        FROM sensor_data
        ORDER BY created_at DESC
        """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for row in rows:
        result.append({
            "id": row[0],
            "node_id": row[1],
            "distance": row[2],
            "temperature": row[3],
            "created_at": row[4]
        })

    return result

# ==============================
# START BACKGROUND COLLECTOR
# ==============================
@app.on_event("startup")
def start_background_tasks():

    create_tables()

    thread = threading.Thread(target=sensor_collector)
    thread.daemon = True
    thread.start()


@app.post("/predict")
def predict_api():

    conn = get_connection()
    cur = conn.cursor()

    # Get last 5 sensor values
    cur.execute("""
    SELECT field1, field2
    FROM sensor_data
    ORDER BY created_at DESC
    LIMIT 5
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    # If no data
    if len(rows) == 0:
        return {"error": "No sensor data available"}

    # Repeat rows until we have 30
    while len(rows) < 30:
        rows = rows + rows

    rows = rows[:30]
    rows = rows[::-1]

    # Convert to features
    features = []
    for r in rows:
        features.append(float(r[0]))
        features.append(float(r[1]))

    # Predict
    result = predict(features)
     # Save prediction
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
     INSERT INTO predictions (input_data, prediction)
    VALUES (%s, %s)
    """, (json.dumps(features), result))

    conn.commit()
    cur.close()
    conn.close()

     

    # Return response
    return {
        "prediction": result,
        "used_points": len(rows)
    }
@app.get("/prediction-history")
def get_predictions():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT id, prediction, created_at
    FROM predictions
    ORDER BY created_at DESC
    LIMIT 10
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "prediction": row[1],
            "created_at": row[2]
        })

    return result
# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
