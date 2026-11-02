
from database import get_db
from datetime import date, timedelta

conn = get_db()
cursor = conn.cursor()

# Insert stations
stations = [
    ("HYB", "Hyderabad Deccan", "Hyderabad"),
    ("SC", "Secunderabad Junction", "Secunderabad"),
    ("VJA", "Vijayawada Junction", "Vijayawada"),
    ("RJY", "Rajahmundry", "Rajahmundry"),
    ("VSKP", "Visakhapatnam Junction", "Visakhapatnam"),
    ("MAS", "Chennai Central", "Chennai")
]

cursor.executemany("""
    INSERT OR IGNORE INTO stations
    (station_code, station_name, city)
    VALUES (?, ?, ?)
""", stations)

conn.commit()

# Get station IDs
def station_id(code):
    result = cursor.execute(
        "SELECT station_id FROM stations WHERE station_code = ?",
        (code,)
    ).fetchone()
    return result["station_id"]

# Insert trains
trains = [
    ("12727", "Godavari Express", "HYB", "VSKP", "17:30", "06:00", 100, 650),
    ("12740", "Garib Rath Express", "SC", "VSKP", "20:15", "08:30", 100, 550),
    ("12760", "Charminar Express", "HYB", "MAS", "18:00", "08:00", 100, 720),
    ("12706", "Intercity Express", "SC", "VJA", "06:00", "12:30", 80, 350),
    ("12728", "Godavari Express", "VSKP", "HYB", "17:20", "05:50", 100, 650),
    ("12806", "Janmabhoomi Express", "VSKP", "SC", "06:15", "18:30", 90, 480)
]

for train in trains:
    number, name, source, destination, departure, arrival, seats, fare = train

    cursor.execute("""
        INSERT OR IGNORE INTO trains
        (train_number, train_name, source_id, destination_id,
         departure_time, arrival_time, total_seats, fare)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        number, name, station_id(source), station_id(destination),
        departure, arrival, seats, fare
    ))

conn.commit()

# Create train runs for the next 15 days
all_trains = cursor.execute(
    "SELECT train_id, total_seats FROM trains"
).fetchall()

for train in all_trains:
    for i in range(15):
        journey_date = (date.today() + timedelta(days=i)).isoformat()

        cursor.execute("""
            INSERT OR IGNORE INTO train_runs
            (train_id, journey_date, available_seats)
            VALUES (?, ?, ?)
        """, (
            train["train_id"],
            journey_date,
            train["total_seats"]
        ))

conn.commit()
conn.close()

print("Sample stations, trains and journey dates inserted!")
