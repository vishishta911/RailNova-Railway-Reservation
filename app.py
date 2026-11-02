
from flask import Flask, render_template, request, redirect, url_for, session
from database import initialize_db, get_db
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from flask import flash
app = Flask(__name__)
app.secret_key = "railnova-development-key-change-before-deployment"

initialize_db()


# HOME PAGE
@app.route("/")
def home():
    return render_template("index.html")


# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():

    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            error = "Please fill all fields."

        elif len(password) < 6:
            error = "Password must contain at least 6 characters."

        else:
            conn = get_db()

            existing = conn.execute(
                "SELECT user_id FROM users WHERE email = ?",
                (email,)
            ).fetchone()

            if existing:
                error = "Email is already registered."
            else:
                cursor = conn.execute("""
                    INSERT INTO users (name, email, password, role)
                    VALUES (?, ?, ?, 'passenger')
                """, (
                    name,
                    email,
                    generate_password_hash(password)
                ))

                conn.commit()

                session["user_id"] = cursor.lastrowid
                session["user_name"] = name
                session["role"] = "passenger"

                conn.close()
                return redirect(url_for("home"))

            conn.close()

    return render_template("register.html", error=error)


# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():

    error = None
    next_page = request.args.get("next", "")

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        next_page = request.form.get("next", "")

        conn = get_db()

        user = conn.execute("""
            SELECT * FROM users
            WHERE email = ?
        """, (email,)).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session.clear()
            session["user_id"] = user["user_id"]
            session["user_name"] = user["name"]
            session["role"] = user["role"]

            if next_page.startswith("/") and not next_page.startswith("//"):
                return redirect(next_page)

            return redirect(url_for("home"))

        error = "Invalid email or password."

    return render_template(
        "login.html",
        error=error,
        next_page=next_page
    )


# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# TRAIN SEARCH
@app.route("/trains")
def search_trains():

    source = request.args.get("source", "").strip()
    destination = request.args.get("destination", "").strip()
    journey_date = request.args.get("date", "").strip()

    if not source or not destination or not journey_date:
        return "Please enter all search details.", 400

    conn = get_db()

    trains = conn.execute("""
        SELECT
            t.train_id,
            t.train_number,
            t.train_name,
            s1.station_name AS source_name,
            s2.station_name AS destination_name,
            t.departure_time,
            t.arrival_time,
            t.total_seats,
            t.fare,
            r.run_id,
            r.available_seats,
            r.journey_date
        FROM trains t
        JOIN stations s1 ON t.source_id = s1.station_id
        JOIN stations s2 ON t.destination_id = s2.station_id
        JOIN train_runs r ON t.train_id = r.train_id
        WHERE
            (LOWER(s1.city) = LOWER(?) OR
             LOWER(s1.station_name) = LOWER(?) OR
             LOWER(s1.station_code) = LOWER(?))
            AND
            (LOWER(s2.city) = LOWER(?) OR
             LOWER(s2.station_name) = LOWER(?) OR
             LOWER(s2.station_code) = LOWER(?))
            AND r.journey_date = ?
            AND r.available_seats > 0
        ORDER BY t.departure_time
    """, (
        source, source, source,
        destination, destination, destination,
        journey_date
    )).fetchall()

    conn.close()

    return render_template(
        "trains.html",
        trains=trains,
        source=source,
        destination=destination,
        journey_date=journey_date
    )


# CANCEL TICKET
@app.route("/cancel/<int:booking_id>", methods=["POST"])
def cancel_ticket(booking_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    try:
        conn.execute("BEGIN IMMEDIATE")

        booking = conn.execute("""
            SELECT booking_id, run_id, passenger_count, status
            FROM bookings
            WHERE booking_id = ? AND user_id = ?
        """, (booking_id, session["user_id"])).fetchone()

        if booking is None:
            conn.rollback()
            flash("Booking not found.")
        
        elif booking["status"] != "CONFIRMED":
            conn.rollback()
            flash("This ticket has already been cancelled.")

        else:
            conn.execute("""
                UPDATE bookings
                SET status = 'CANCELLED'
                WHERE booking_id = ?
            """, (booking_id,))

            conn.execute("""
                UPDATE train_runs
                SET available_seats =
                    MIN(
                        available_seats + ?,
                        (SELECT total_seats
                         FROM trains
                         JOIN train_runs USING(train_id)
                         WHERE run_id = ?)
                    )
                WHERE run_id = ?
            """, (
                booking["passenger_count"],
                booking["run_id"],
                booking["run_id"]
            ))

            conn.commit()
            flash("Ticket cancelled successfully! Seat availability restored.")
        
        return redirect(url_for("my_bookings"))

    except Exception:
        conn.rollback()
        app.logger.exception("Cancellation failed")
        flash("Unable to cancel ticket. Please try again.")
        return redirect(url_for("my_bookings"))

    finally:
        conn.close()

# PNR STATUS
@app.route("/pnr", methods=["GET", "POST"])
def pnr_status():

    booking = None
    error = None

    if request.method == "POST":

        pnr = request.form.get("pnr", "").strip().upper()

        if not pnr:
            error = "Please enter a PNR number."
        else:
            conn = get_db()

            booking = conn.execute("""
                SELECT
                    b.pnr,
                    b.status,
                    b.total_fare,
                    r.journey_date,
                    t.train_name,
                    t.train_number,
                    s1.station_name AS source_name,
                    s2.station_name AS destination_name,
                    p.passenger_name,
                    p.age,
                    p.gender,
                    p.seat_number
                FROM bookings b
                JOIN train_runs r ON b.run_id = r.run_id
                JOIN trains t ON r.train_id = t.train_id
                JOIN stations s1 ON t.source_id = s1.station_id
                JOIN stations s2 ON t.destination_id = s2.station_id
                LEFT JOIN passengers p ON b.booking_id = p.booking_id
                WHERE b.pnr = ?
            """, (pnr,)).fetchone()

            conn.close()

            if booking is None:
                error = "No booking found with this PNR number."

    return render_template(
        "pnr.html",
        booking=booking,
        error=error
    )

# BOOK TICKET
@app.route("/book/<int:run_id>", methods=["GET", "POST"])
def book_ticket(run_id):

    if "user_id" not in session:
        return redirect(url_for("login", next=request.path))

    conn = get_db()

    train = conn.execute("""
        SELECT
            r.run_id,
            r.journey_date,
            r.available_seats,
            t.train_name,
            t.fare,
            s1.station_name AS source_name,
            s2.station_name AS destination_name
        FROM train_runs r
        JOIN trains t ON r.train_id = t.train_id
        JOIN stations s1 ON t.source_id = s1.station_id
        JOIN stations s2 ON t.destination_id = s2.station_id
        WHERE r.run_id = ?
    """, (run_id,)).fetchone()

    if train is None:
        conn.close()
        return "Train journey not found.", 404

    if request.method == "GET":
        conn.close()
        return render_template("booking.html", train=train, error=None)

    name = request.form.get("passenger_name", "").strip()
    age = request.form.get("age", "")
    gender = request.form.get("gender", "")

    try:
        age = int(age)
    except (ValueError, TypeError):
        age = 0

    if not name or not (1 <= age <= 120) or gender not in (
        "Male", "Female", "Other"
    ):
        conn.close()
        return render_template(
            "booking.html",
            train=train,
            error="Please enter valid passenger details."
        )

    try:
        conn.execute("BEGIN IMMEDIATE")

        current = conn.execute("""
            SELECT available_seats
            FROM train_runs
            WHERE run_id = ?
        """, (run_id,)).fetchone()

        if current is None or current["available_seats"] <= 0:
            conn.rollback()
            conn.close()
            return render_template(
                "booking.html",
                train=train,
                error="Sorry! No seats are available."
            )

        seat_number = current["available_seats"]
        pnr = "RN" + secrets.token_hex(5).upper()

        cursor = conn.execute("""
            INSERT INTO bookings
            (pnr, user_id, run_id, passenger_count, total_fare, status)
            VALUES (?, ?, ?, 1, ?, 'CONFIRMED')
        """, (
            pnr,
            session["user_id"],
            run_id,
            train["fare"]
        ))

        booking_id = cursor.lastrowid

        conn.execute("""
            INSERT INTO passengers
            (booking_id, passenger_name, age, gender, seat_number)
            VALUES (?, ?, ?, ?, ?)
        """, (booking_id, name, age, gender, str(seat_number)))

        conn.execute("""
            UPDATE train_runs
            SET available_seats = available_seats - 1
            WHERE run_id = ?
        """, (run_id,))

        conn.commit()

        return render_template(
            "booking_success.html",
            pnr=pnr,
            name=name,
            train=train,
            seat_number=seat_number,
            fare=train["fare"]
        )

    except Exception:
        conn.rollback()
        app.logger.exception("Booking failed")
        return "Booking failed. Please try again.", 500

    finally:
        conn.close()


# MY BOOKINGS
@app.route("/my-bookings")
def my_bookings():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    bookings = conn.execute("""       
        SELECT
            b.booking_id,
            b.pnr,
            b.total_fare,
            b.status,
            r.journey_date,
            t.train_name,
            t.train_number,
            s1.station_name AS source_name,
            s2.station_name AS destination_name,
            p.passenger_name,
            p.seat_number
        FROM bookings b
        JOIN train_runs r ON b.run_id = r.run_id
        JOIN trains t ON r.train_id = t.train_id
        JOIN stations s1 ON t.source_id = s1.station_id
        JOIN stations s2 ON t.destination_id = s2.station_id
        LEFT JOIN passengers p ON b.booking_id = p.booking_id
        WHERE b.user_id = ?
        ORDER BY b.booking_id DESC

    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template("my_bookings.html", bookings=bookings)


@app.route("/health")
def health():
    return {"status": "RailNova is running!"}


# ADMIN ACCESS CHECK
def admin_required():
    return session.get("role") == "admin"


# ADMIN DASHBOARD
@app.route("/admin")
def admin_dashboard():

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    stats = conn.execute("""
        SELECT
            (SELECT COUNT(*) FROM trains) AS total_trains,
            (SELECT COUNT(*) FROM users WHERE role='passenger') AS total_passengers,
            (SELECT COUNT(*) FROM bookings) AS total_bookings,
            (SELECT COUNT(*) FROM bookings
             WHERE status='CONFIRMED') AS confirmed_bookings,
            (SELECT COALESCE(SUM(total_fare), 0)
             FROM bookings WHERE status='CONFIRMED') AS revenue
    """).fetchone()

    trains = conn.execute("""
        SELECT
            t.train_id,
            t.train_number,
            t.train_name,
            s1.station_name AS source_name,
            s2.station_name AS destination_name,
            t.departure_time,
            t.arrival_time,
            t.fare,
            t.total_seats
        FROM trains t
        JOIN stations s1 ON t.source_id = s1.station_id
        JOIN stations s2 ON t.destination_id = s2.station_id
        ORDER BY t.train_number
    """).fetchall()

    bookings = conn.execute("""
        SELECT
            b.pnr,
            b.status,
            b.total_fare,
            r.journey_date,
            t.train_name,
            u.name AS passenger_name
        FROM bookings b
        JOIN train_runs r ON b.run_id = r.run_id
        JOIN trains t ON r.train_id = t.train_id
        JOIN users u ON b.user_id = u.user_id
        ORDER BY b.booking_id DESC
    """).fetchall()

    stations = conn.execute("""
        SELECT * FROM stations ORDER BY station_name
    """).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        stats=stats,
        trains=trains,
        bookings=bookings,
        stations=stations
    )


# ADD NEW TRAIN
@app.route("/admin/add-train", methods=["POST"])
def add_train():

    if not admin_required():
        return redirect(url_for("login"))

    number = request.form.get("train_number", "").strip()
    name = request.form.get("train_name", "").strip()
    source = request.form.get("source_id", "")
    destination = request.form.get("destination_id", "")
    departure = request.form.get("departure_time", "")
    arrival = request.form.get("arrival_time", "")
    seats = request.form.get("total_seats", "")
    fare = request.form.get("fare", "")

    try:
        source = int(source)
        destination = int(destination)
        seats = int(seats)
        fare = float(fare)

        if (not number or not name or not departure or not arrival
                or source == destination or seats <= 0 or fare <= 0):
            raise ValueError

        conn = get_db()

        cursor = conn.execute("""
            INSERT INTO trains
            (train_number, train_name, source_id, destination_id,
             departure_time, arrival_time, total_seats, fare)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            number, name, source, destination,
            departure, arrival, seats, fare
        ))

        train_id = cursor.lastrowid

        from datetime import date, timedelta

        for i in range(30):
            journey_date = (
                date.today() + timedelta(days=i)
            ).isoformat()

            conn.execute("""
                INSERT INTO train_runs
                (train_id, journey_date, available_seats)
                VALUES (?, ?, ?)
            """, (train_id, journey_date, seats))

        conn.commit()
        conn.close()

        flash("Train added successfully!")

    except (ValueError, TypeError):
        flash("Please enter valid train details.")
    except Exception:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        app.logger.exception("Unable to add train")
        flash("Unable to add train. Check the train number and station details.")

    return redirect(url_for("admin_dashboard"))

if __name__ == "__main__":
    app.run(debug=True)
