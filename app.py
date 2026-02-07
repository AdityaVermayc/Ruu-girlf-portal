ENV = os.environ.get("ENV", "development")

from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_mail import Mail, Message
import psycopg2
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# =======================
# Mail configuration
# =======================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_ADMIN')
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('EMAIL_DEFAULT_SENDER')

mail = Mail(app)

# =======================
# Environment variables
# =======================
USER_NAME = os.environ.get('USER_NAME')
USER_PASSWORD = os.environ.get('USER_PASSWORD')

ADMIN_NAME = os.environ.get('ADMIN_NAME')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

PORTAL_URL = os.environ.get('PORTAL_URL')
DATABASE_URL = os.environ.get('DATABASE_URL')

# =======================
# Database helpers
# =======================
def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )

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

# =======================
# Auth decorator
# =======================
def login_required(role):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if 'user' not in session or session.get('user') != role:
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

# =======================
# Routes
# =======================
@app.route('/')
def home():
    return render_template('home.html', user_display_name=USER_NAME)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pw = request.form['password']

        if user == USER_NAME and pw == USER_PASSWORD:
            session['user'] = USER_NAME
            return redirect(url_for('submit'))

        elif user == ADMIN_NAME and pw == ADMIN_PASSWORD:
            session['user'] = ADMIN_NAME
            return redirect(url_for('dashboard'))

        else:
            flash('Invalid credentials')

    return render_template('login.html', user_display_name=USER_NAME)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

# =======================
# Submit grievance
# =======================
@app.route('/submit', methods=['GET', 'POST'])
@login_required(USER_NAME)
def submit():
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['description']
        mood = request.form['mood']
        priority = request.form['priority']

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO grievances (title, description, mood, priority)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (title, desc, mood, priority)
        )

        grievance_id = cur.fetchone()[0]

        conn.commit()
        cur.close()
        conn.close()

        # Email admin
        msg = Message(
            f"New Grievance from {USER_NAME} 💌",
            recipients=[os.environ.get('EMAIL_ADMIN')]
        )

        msg.html = f"""
        <h3>New Grievance Submitted 💌</h3>
        <p><strong>Title:</strong> {title}</p>
        <p><strong>Mood:</strong> {mood}</p>
        <p><strong>Priority:</strong> {priority}</p>
        <p><strong>Description:</strong><br>{desc}</p>
        """

        if os.environ.get("ENV") != "production":
    mail.send(msg)
else:
    print("Skipping email send in production")


        flash(f"Grievance submitted! {ADMIN_NAME} has been notified 💌")
        return redirect(url_for('thank_you'))

    return render_template('submit.html')

# =======================
# Thank you
# =======================
@app.route('/thankyou')
@login_required(USER_NAME)
def thank_you():
    return render_template(
        'thankyou.html',
        user_display_name=USER_NAME,
        admin_display_name=ADMIN_NAME
    )

# =======================
# User grievances
# =======================
@app.route('/my_grievances')
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
    return render_template('my_grievances.html', grievances=data)

# =======================
# Admin dashboard
# =======================
@app.route('/dashboard')
@login_required(ADMIN_NAME)
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM grievances ORDER BY created_at DESC")
    data = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('dashboard.html', grievances=data)

# =======================
# Admin respond
# =======================
@app.route('/respond/<int:gid>', methods=['POST'])
@login_required(ADMIN_NAME)
def respond(gid):
    response = request.form['response']

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE grievances SET response = %s WHERE id = %s",
        (response, gid)
    )

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('dashboard'))

# =======================
# Mark resolved
# =======================
@app.route('/resolve/<int:gid>')
@login_required(ADMIN_NAME)
def resolve(gid):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE grievances SET status = 'Resolved' WHERE id = %s",
        (gid,)
    )

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('dashboard'))

# =======================
# App start
# =======================
init_db()  # <-- THIS is the fix

if __name__ == '__main__':
    app.run(debug=True)
