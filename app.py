import os
from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_mail import Mail, Message
import psycopg2
from functools import wraps

# ======================
# Environment
# ======================
ENV = os.environ.get("ENV", "development")

# ======================
# App setup
# ======================
app = Flask(__name__)
app.secret_key = "supersecretkey"

# ======================
# Mail config (DISABLED in prod)
# ======================
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("EMAIL_ADMIN")
app.config["MAIL_PASSWORD"] = os.environ.get("EMAIL_PASS")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("EMAIL_ADMIN")

mail = Mail(app)

# ======================
# App variables
# ======================
USER_NAME = os.environ.get("USER_NAME", "Guest")
USER_PASSWORD = os.environ.get("USER_PASSWORD", "password")

ADMIN_NAME = os.environ.get("ADMIN_NAME", "Admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

DATABASE_URL = os.environ.get("DATABASE_URL")

# ======================
# Database helpers
# ======================
def get_db_connection():
    if ENV != "production":
        raise RuntimeError("Database only available in production")
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS grievances (
            id SERIAL PRIMARY KEY,
            title TEXT,
            description TEXT,
            mood TEXT,
            priority TEXT,
            response TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

# ======================
# Auth decorator
# ======================
def login_required(role):
    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            if session.get("user") != role:
                return redirect(url_for("login"))
            return fn(*args, **kwargs)
        return decorated
    return wrapper

# ======================
# Routes
# ======================
@app.route("/")
def home():
    return render_template("home.html", user_display_name=USER_NAME)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        if u == USER_NAME and p == USER_PASSWORD:
            session["user"] = USER_NAME
            return redirect(url_for("submit"))

        if u == ADMIN_NAME and p == ADMIN_PASSWORD:
            session["user"] = ADMIN_NAME
            return redirect(url_for("dashboard"))

        flash("Invalid credentials")

    return render_template("login.html", user_display_name=USER_NAME)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ======================
# Submit grievance
# ======================
@app.route("/submit", methods=["GET", "POST"])
@login_required(USER_NAME)
def submit():
    if request.method == "POST":
        print("SUBMIT HIT")

        title = request.form["title"]
        desc = request.form["description"]
        mood = request.form["mood"]
        priority = request.form["priority"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO grievances (title, description, mood, priority)
            VALUES (%s, %s, %s, %s)
            """,
            (title, desc, mood, priority)
        )
        conn.commit()
        cur.close()
        conn.close()

        print("DB INSERT SUCCESS")

        # 🔒 EMAIL DISABLED (Railway blocks SMTP)
        print("EMAIL SKIPPED")

        flash("Grievance submitted 💌")
        print("REDIRECTING")
        return redirect(url_for("thank_you"))

    return render_template("submit.html")

@app.route("/thankyou")
@login_required(USER_NAME)
def thank_you():
    return render_template(
        "thankyou.html",
        user_display_name=USER_NAME,
        admin_display_name=ADMIN_NAME
    )

# ======================
# User grievances
# ======================
@app.route("/my_grievances")
@login_required(USER_NAME)
def my_grievances():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT title, description, mood, priority, response, status
        FROM grievances
        ORDER BY created_at DESC
    """)
    data = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("my_grievances.html", grievances=data)

# ======================
# Admin dashboard
# ======================
@app.route("/dashboard")
@login_required(ADMIN_NAME)
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM grievances ORDER BY created_at DESC")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("dashboard.html", grievances=data)

@app.route("/resolve/<int:gid>")
@login_required(ADMIN_NAME)
def resolve(gid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE grievances SET status='Resolved' WHERE id=%s",
        (gid,)
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("dashboard"))

# ======================
# App start
# ======================
if __name__ == "__main__":
    if ENV == "production":
        init_db()
    app.run(debug=True)

