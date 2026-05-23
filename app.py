"""
Smart Attendance System
=======================
QR-code based attendance tracking web app.
- Generates unique per-session QR codes
- Students scan QR to mark attendance
- Real-time dashboard for faculty
- REST API for integration
- SQLite backend (Firebase-ready)
"""

from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
import sqlite3, qrcode, base64, io, os, uuid, hashlib
from datetime import datetime, date
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)
DB_PATH = "attendance.db"


# ─────────────────────────────────────────────
# Database setup
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            role        TEXT DEFAULT 'student',
            roll_no     TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            subject     TEXT NOT NULL,
            faculty_id  TEXT NOT NULL,
            date        TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT,
            qr_token    TEXT UNIQUE NOT NULL,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            student_id  TEXT NOT NULL,
            marked_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_id, student_id)
        );
    """)

    # Seed demo users
    seed_users = [
        (str(uuid.uuid4()), "Prof. Sharma", "faculty@demo.com",
         _hash("faculty123"), "faculty", None),
        (str(uuid.uuid4()), "Rudransh Dwivedi", "student1@demo.com",
         _hash("student123"), "student", "2023CSE001"),
        (str(uuid.uuid4()), "Priya Singh", "student2@demo.com",
         _hash("student123"), "student", "2023CSE002"),
        (str(uuid.uuid4()), "Arjun Mehta", "student3@demo.com",
         _hash("student123"), "student", "2023CSE003"),
        (str(uuid.uuid4()), "Sneha Patel", "student4@demo.com",
         _hash("student123"), "student", "2023CSE004"),
    ]
    for u in seed_users:
        try:
            conn.execute(
                "INSERT INTO users (id,name,email,password,role,roll_no) VALUES (?,?,?,?,?,?)", u)
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ─────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


def faculty_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "faculty":
            return jsonify({"error": "Faculty access required"}), 403
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# QR Code generation
# ─────────────────────────────────────────────

def generate_qr(data: str) -> str:
    """Generate QR code and return as base64 PNG string."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=3
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#16a34a", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ─────────────────────────────────────────────
# HTML Templates
# ─────────────────────────────────────────────

BASE_STYLE = """
<style>
:root{--green:#16a34a;--green-dark:#15803d;--bg:#f9fafb;--card:#fff;--border:#e5e7eb;--text:#111827;--muted:#6b7280;--danger:#dc2626}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.nav{background:#fff;border-bottom:1px solid var(--border);padding:0.75rem 1.5rem;display:flex;align-items:center;justify-content:space-between}
.nav-brand{font-weight:700;font-size:1.1rem;color:var(--green)}
.nav-links a{margin-left:1rem;font-size:14px;color:var(--muted);text-decoration:none}
.nav-links a:hover{color:var(--text)}
.container{max-width:1000px;margin:0 auto;padding:1.5rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.5rem;margin-bottom:1rem}
.card-title{font-size:0.8rem;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:var(--muted);margin-bottom:1rem}
.btn{display:inline-flex;align-items:center;gap:6px;padding:9px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none;text-decoration:none}
.btn-primary{background:var(--green);color:#fff}.btn-primary:hover{background:var(--green-dark)}
.btn-danger{background:var(--danger);color:#fff}
.btn-outline{background:#fff;color:var(--text);border:1px solid var(--border)}
.input{width:100%;padding:9px 12px;border:1px solid var(--border);border-radius:8px;font-size:14px;margin-bottom:0.75rem}
.input:focus{outline:2px solid var(--green);border-color:transparent}
.stat-row{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:1rem}
.stat{background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:1rem;text-align:center}
.stat-val{font-size:1.8rem;font-weight:700;color:var(--green)}
.stat-label{font-size:11px;color:var(--muted);margin-top:2px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:8px 12px;background:var(--bg);color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;border-bottom:1px solid var(--border)}
td{padding:10px 12px;border-bottom:1px solid var(--border)}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;font-size:11px;padding:2px 8px;border-radius:100px;font-weight:600}
.badge-green{background:#dcfce7;color:#15803d}
.badge-red{background:#fee2e2;color:#b91c1c}
.badge-blue{background:#dbeafe;color:#1e40af}
.alert{padding:10px 14px;border-radius:8px;margin-bottom:1rem;font-size:13px}
.alert-error{background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5}
.alert-success{background:#dcfce7;color:#15803d;border:1px solid #86efac}
.qr-box{text-align:center;padding:1.5rem}
.qr-box img{border:3px solid var(--green);border-radius:12px;padding:8px;background:#fff}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
@media(max-width:600px){.stat-row{grid-template-columns:repeat(2,1fr)}.grid-2{grid-template-columns:1fr}}
</style>
"""

LOGIN_HTML = BASE_STYLE + """
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#052e16,#14532d)">
<div style="background:#fff;border-radius:16px;padding:2rem;width:100%;max-width:380px;box-shadow:0 20px 60px rgba(0,0,0,0.3)">
  <div style="text-align:center;margin-bottom:1.5rem">
    <div style="font-size:2rem;margin-bottom:0.5rem">📋</div>
    <h1 style="font-size:1.4rem;font-weight:700">Smart Attendance</h1>
    <p style="font-size:13px;color:#6b7280;margin-top:4px">QR-based attendance system</p>
  </div>
  {% if error %}<div class="alert alert-error">{{ error }}</div>{% endif %}
  <form method="POST" action="/login">
    <input class="input" type="email" name="email" placeholder="Email" required>
    <input class="input" type="password" name="password" placeholder="Password" required>
    <button class="btn btn-primary" style="width:100%;justify-content:center">Login →</button>
  </form>
  <div style="margin-top:1rem;padding:12px;background:#f9fafb;border-radius:8px;font-size:12px;color:#6b7280">
    <strong>Demo accounts:</strong><br>
    Faculty: faculty@demo.com / faculty123<br>
    Student: student1@demo.com / student123
  </div>
</div>
</div>
"""

FACULTY_HTML = BASE_STYLE + """
<div class="nav">
  <div class="nav-brand">📋 SmartAttend</div>
  <div class="nav-links">
    <span style="font-size:13px;color:#374151">Welcome, {{ name }}</span>
    <a href="/logout">Logout</a>
  </div>
</div>
<div class="container">
  {% if message %}<div class="alert alert-success">{{ message }}</div>{% endif %}

  <div class="stat-row">
    <div class="stat"><div class="stat-val">{{ stats.total_sessions }}</div><div class="stat-label">Total sessions</div></div>
    <div class="stat"><div class="stat-val">{{ stats.active_sessions }}</div><div class="stat-label">Active now</div></div>
    <div class="stat"><div class="stat-val">{{ stats.total_students }}</div><div class="stat-label">Students enrolled</div></div>
    <div class="stat"><div class="stat-val">{{ stats.today_attendance }}</div><div class="stat-label">Marked today</div></div>
  </div>

  <div class="grid-2">
    <div class="card">
      <div class="card-title">Create New Session</div>
      <form method="POST" action="/sessions/create">
        <input class="input" type="text" name="subject" placeholder="Subject (e.g. Data Structures)" required>
        <input class="input" type="date" name="date" value="{{ today }}" required>
        <input class="input" type="time" name="start_time" value="{{ now_time }}" required>
        <button class="btn btn-primary" type="submit">Generate QR →</button>
      </form>
    </div>

    {% if active_session %}
    <div class="card">
      <div class="card-title">Active Session — {{ active_session.subject }}</div>
      <div class="qr-box">
        <img src="data:image/png;base64,{{ active_session.qr_img }}" width="180" alt="QR Code">
        <p style="font-size:12px;color:#6b7280;margin-top:8px">Students scan this QR to mark attendance</p>
        <p style="font-size:11px;color:#9ca3af;margin-top:4px">Token: {{ active_session.qr_token[:8] }}...</p>
      </div>
      <div style="text-align:center">
        <form method="POST" action="/sessions/{{ active_session.id }}/close">
          <button class="btn btn-danger" type="submit">Close Session</button>
        </form>
      </div>
    </div>
    {% endif %}
  </div>

  <div class="card">
    <div class="card-title">All Sessions</div>
    <table>
      <thead><tr><th>Subject</th><th>Date</th><th>Time</th><th>Attendance</th><th>Status</th><th></th></tr></thead>
      <tbody>
        {% for s in sessions %}
        <tr>
          <td><strong>{{ s.subject }}</strong></td>
          <td>{{ s.date }}</td>
          <td>{{ s.start_time }}</td>
          <td><span class="badge badge-blue">{{ s.count }} students</span></td>
          <td>{% if s.is_active %}<span class="badge badge-green">Active</span>{% else %}<span class="badge" style="background:#f3f4f6;color:#6b7280">Closed</span>{% endif %}</td>
          <td><a href="/sessions/{{ s.id }}" class="btn btn-outline" style="font-size:11px;padding:4px 10px">View</a></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
"""

STUDENT_HTML = BASE_STYLE + """
<div class="nav">
  <div class="nav-brand">📋 SmartAttend</div>
  <div class="nav-links">
    <span style="font-size:13px;color:#374151">{{ name }} ({{ roll_no }})</span>
    <a href="/logout">Logout</a>
  </div>
</div>
<div class="container">
  {% if message %}<div class="alert alert-success">{{ message }}</div>{% endif %}
  {% if error %}<div class="alert alert-error">{{ error }}</div>{% endif %}

  <div class="grid-2" style="margin-bottom:1rem">
    <div class="stat" style="background:#fff;border:1px solid var(--border);border-radius:10px;padding:1.5rem;text-align:center">
      <div class="stat-val">{{ my_stats.total_marked }}</div>
      <div class="stat-label">Classes attended</div>
    </div>
    <div class="stat" style="background:#fff;border:1px solid var(--border);border-radius:10px;padding:1.5rem;text-align:center">
      <div class="stat-val" style="color:{% if my_stats.pct >= 75 %}var(--green){% else %}var(--danger){% endif %}">{{ my_stats.pct }}%</div>
      <div class="stat-label">Overall attendance</div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Mark Attendance</div>
    <p style="font-size:13px;color:var(--muted);margin-bottom:1rem">Enter the QR code token displayed by your faculty, or scan the QR code.</p>
    <form method="POST" action="/attendance/mark">
      <input class="input" type="text" name="qr_token" placeholder="Enter QR token or scan QR" required>
      <button class="btn btn-primary" type="submit">✓ Mark Present</button>
    </form>
  </div>

  <div class="card">
    <div class="card-title">My Attendance Record</div>
    <table>
      <thead><tr><th>Subject</th><th>Date</th><th>Time</th><th>Status</th></tr></thead>
      <tbody>
        {% for r in records %}
        <tr>
          <td><strong>{{ r.subject }}</strong></td>
          <td>{{ r.date }}</td>
          <td>{{ r.start_time }}</td>
          <td><span class="badge badge-green">Present ✓</span></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
"""

# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

from jinja2 import Template

def render(template_str, **ctx):
    return Template(template_str).render(**ctx)


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect("/login")
    if session.get("role") == "faculty":
        return redirect("/faculty")
    return redirect("/student")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = _hash(request.form.get("password", ""))
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?", (email, password)
        ).fetchone()
        conn.close()
        if user:
            session["user_id"] = user["id"]
            session["name"]    = user["name"]
            session["role"]    = user["role"]
            session["roll_no"] = user["roll_no"]
            return redirect("/")
        return render(LOGIN_HTML, error="Invalid credentials")
    return render(LOGIN_HTML, error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/faculty")
@login_required
def faculty_dashboard():
    conn = get_db()
    faculty_id = session["user_id"]

    sessions_raw = conn.execute("""
        SELECT s.*, COUNT(a.id) as count
        FROM sessions s
        LEFT JOIN attendance a ON a.session_id = s.id
        WHERE s.faculty_id = ?
        GROUP BY s.id
        ORDER BY s.created_at DESC
    """, (faculty_id,)).fetchall()

    active_raw = conn.execute(
        "SELECT * FROM sessions WHERE faculty_id=? AND is_active=1 ORDER BY created_at DESC LIMIT 1",
        (faculty_id,)
    ).fetchone()

    stats = {
        "total_sessions":  len(sessions_raw),
        "active_sessions": sum(1 for s in sessions_raw if s["is_active"]),
        "total_students":  conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        "today_attendance": conn.execute("""
            SELECT COUNT(*) FROM attendance a
            JOIN sessions s ON a.session_id = s.id
            WHERE s.faculty_id=? AND DATE(a.marked_at)=DATE('now')
        """, (faculty_id,)).fetchone()[0]
    }
    conn.close()

    active_session = None
    if active_raw:
        mark_url = f"http://localhost:5002/attendance/mark?token={active_raw['qr_token']}"
        active_session = {
            "id":        active_raw["id"],
            "subject":   active_raw["subject"],
            "qr_token":  active_raw["qr_token"],
            "qr_img":    generate_qr(mark_url),
            "is_active": active_raw["is_active"]
        }

    return render(FACULTY_HTML,
                  name=session["name"],
                  sessions=[dict(s) for s in sessions_raw],
                  active_session=active_session,
                  stats=stats,
                  today=date.today().isoformat(),
                  now_time=datetime.now().strftime("%H:%M"),
                  message=request.args.get("msg"))


@app.route("/sessions/create", methods=["POST"])
@login_required
def create_session():
    subject    = request.form.get("subject", "").strip()
    date_str   = request.form.get("date")
    start_time = request.form.get("start_time")
    if not subject:
        return redirect("/faculty")

    session_id = str(uuid.uuid4())
    qr_token   = str(uuid.uuid4()).replace("-", "")[:16].upper()

    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (id,subject,faculty_id,date,start_time,qr_token) VALUES (?,?,?,?,?,?)",
        (session_id, subject, session["user_id"], date_str, start_time, qr_token)
    )
    conn.commit()
    conn.close()
    return redirect(f"/faculty?msg=Session+created+for+{subject}")


@app.route("/sessions/<session_id>/close", methods=["POST"])
@login_required
def close_session(session_id):
    conn = get_db()
    conn.execute(
        "UPDATE sessions SET is_active=0, end_time=? WHERE id=? AND faculty_id=?",
        (datetime.now().strftime("%H:%M"), session_id, session["user_id"])
    )
    conn.commit()
    conn.close()
    return redirect("/faculty?msg=Session+closed")


@app.route("/sessions/<session_id>")
@login_required
def session_detail(session_id):
    conn = get_db()
    sess   = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    marked = conn.execute("""
        SELECT u.name, u.roll_no, a.marked_at
        FROM attendance a JOIN users u ON a.student_id = u.id
        WHERE a.session_id=?
        ORDER BY a.marked_at
    """, (session_id,)).fetchall()
    conn.close()
    if not sess:
        return redirect("/faculty")

    rows = "".join(f"<tr><td>{r['name']}</td><td>{r['roll_no']}</td><td>{r['marked_at']}</td>"
                   f"<td><span class='badge badge-green'>Present ✓</span></td></tr>"
                   for r in marked)
    html = BASE_STYLE + f"""
    <div class="nav"><div class="nav-brand">📋 SmartAttend</div>
    <div class="nav-links"><a href="/faculty">← Back</a><a href="/logout">Logout</a></div></div>
    <div class="container">
    <div class="card"><div class="card-title">{sess['subject']} — {sess['date']}</div>
    <p style="font-size:13px;color:#6b7280;margin-bottom:1rem">
      {len(marked)} student(s) marked present &nbsp;|&nbsp;
      Started: {sess['start_time']} &nbsp;|&nbsp;
      {'<span class="badge badge-green">Active</span>' if sess['is_active'] else '<span class="badge" style="background:#f3f4f6;color:#6b7280">Closed</span>'}
    </p>
    <table><thead><tr><th>Name</th><th>Roll No.</th><th>Marked At</th><th>Status</th></tr></thead>
    <tbody>{rows if rows else '<tr><td colspan="4" style="text-align:center;color:#9ca3af;padding:1.5rem">No attendance marked yet</td></tr>'}</tbody></table>
    </div></div>"""
    return html


@app.route("/student")
@login_required
def student_dashboard():
    conn = get_db()
    records = conn.execute("""
        SELECT s.subject, s.date, s.start_time FROM attendance a
        JOIN sessions s ON a.session_id = s.id
        WHERE a.student_id=?
        ORDER BY s.date DESC, s.start_time DESC
    """, (session["user_id"],)).fetchall()

    total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    conn.close()

    pct = round(len(records) / max(total_sessions, 1) * 100, 1)
    return render(STUDENT_HTML,
                  name=session["name"],
                  roll_no=session.get("roll_no", ""),
                  records=[dict(r) for r in records],
                  my_stats={"total_marked": len(records), "pct": pct},
                  message=request.args.get("msg"),
                  error=request.args.get("err"))


@app.route("/attendance/mark", methods=["POST", "GET"])
@login_required
def mark_attendance():
    if session.get("role") != "student":
        return redirect("/faculty")

    token = request.form.get("qr_token") or request.args.get("token", "")
    token = token.strip().upper()

    conn = get_db()
    sess = conn.execute(
        "SELECT * FROM sessions WHERE qr_token=? AND is_active=1", (token,)
    ).fetchone()

    if not sess:
        conn.close()
        return redirect("/student?err=Invalid+or+expired+QR+token")

    try:
        att_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO attendance (id,session_id,student_id) VALUES (?,?,?)",
            (att_id, sess["id"], session["user_id"])
        )
        conn.commit()
        conn.close()
        return redirect(f"/student?msg=Attendance+marked+for+{sess['subject']}")
    except sqlite3.IntegrityError:
        conn.close()
        return redirect("/student?err=Attendance+already+marked+for+this+session")


# ─────────────────────────────────────────────
# REST API
# ─────────────────────────────────────────────

@app.route("/api/sessions", methods=["GET"])
def api_sessions():
    conn = get_db()
    sessions = conn.execute(
        "SELECT id,subject,date,start_time,is_active FROM sessions ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return jsonify([dict(s) for s in sessions])


@app.route("/api/sessions/<session_id>/attendance")
def api_attendance(session_id):
    conn = get_db()
    records = conn.execute("""
        SELECT u.name, u.roll_no, a.marked_at
        FROM attendance a JOIN users u ON a.student_id = u.id
        WHERE a.session_id=?
    """, (session_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in records])


@app.route("/health")
def health():
    return jsonify({"status": "ok", "db": DB_PATH})


if __name__ == "__main__":
    init_db()
    print("[✓] Database initialised")
    print("[✓] Demo: faculty@demo.com / faculty123")
    print("[✓] Demo: student1@demo.com / student123")
    app.run(debug=True, host="0.0.0.0", port=5002)
