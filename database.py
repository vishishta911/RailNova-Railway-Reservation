
import sqlite3

DATABASE = "railnova.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def initialize_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'passenger'
    );

    CREATE TABLE IF NOT EXISTS stations (
        station_id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_code TEXT UNIQUE NOT NULL,
        station_name TEXT NOT NULL,
        city TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS trains (
        train_id INTEGER PRIMARY KEY AUTOINCREMENT,
        train_number TEXT UNIQUE NOT NULL,
        train_name TEXT NOT NULL,
        source_id INTEGER NOT NULL,
        destination_id INTEGER NOT NULL,
        departure_time TEXT NOT NULL,
        arrival_time TEXT NOT NULL,
        total_seats INTEGER NOT NULL,
        fare REAL NOT NULL,
        FOREIGN KEY(source_id) REFERENCES stations(station_id),
        FOREIGN KEY(destination_id) REFERENCES stations(station_id)
    );

    CREATE TABLE IF NOT EXISTS train_runs (
        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
        train_id INTEGER NOT NULL,
        journey_date TEXT NOT NULL,
        available_seats INTEGER NOT NULL,
        UNIQUE(train_id, journey_date),
        FOREIGN KEY(train_id) REFERENCES trains(train_id)
    );

    CREATE TABLE IF NOT EXISTS bookings (
        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        pnr TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        run_id INTEGER NOT NULL,
        passenger_count INTEGER NOT NULL,
        total_fare REAL NOT NULL,
        status TEXT DEFAULT 'CONFIRMED',
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(run_id) REFERENCES train_runs(run_id)
    );

    CREATE TABLE IF NOT EXISTS passengers (
        passenger_id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        passenger_name TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT,
        seat_number TEXT,
        FOREIGN KEY(booking_id) REFERENCES bookings(booking_id)
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialize_db()
    print("RailNova database initialized!")
