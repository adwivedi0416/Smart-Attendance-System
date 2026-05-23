# 📋 Smart Attendance System

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite)](https://sqlite.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

A QR-code based attendance tracking system for educational institutions. Faculty generate session QR codes; students scan them to mark attendance. Real-time dashboards for both roles.

---

## ✨ Features

**For Faculty**
- Generate unique QR codes per class session in one click
- Real-time attendance dashboard — see who's marked present live
- Session history with per-session attendance lists
- Open/close sessions to control the attendance window

**For Students**
- Scan QR code or enter token to mark attendance instantly
- Personal attendance record with percentage tracking
- 75% attendance alert indicator

**System**
- Role-based auth (faculty / student)
- SQLite backend — zero config, Firebase-ready to replace
- REST API for external integrations
- Agile-built with iterative UI testing

---

## 🚀 Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/smart-attendance-system.git
cd smart-attendance-system
pip install -r requirements.txt
python app.py
# Open http://localhost:5002
```

**Demo credentials:**
| Role | Email | Password |
|---|---|---|
| Faculty | faculty@demo.com | faculty123 |
| Student | student1@demo.com | student123 |

---

## 🏗️ Architecture

```
Faculty Dashboard          Student Dashboard
      │                           │
      ▼                           ▼
 Create Session            Scan QR / Enter Token
      │                           │
      ▼                           ▼
 Generate QR Code ──────► Mark Attendance (REST)
      │                           │
      └───────────────┬───────────┘
                      ▼
               SQLite Database
               (Firebase-ready)
                      │
                      ▼
              Analytics Dashboard
```

---

## 🔌 REST API

```bash
# Get all sessions
GET /api/sessions

# Get attendance for a session
GET /api/sessions/{session_id}/attendance

# Health check
GET /health
```

**Sample response:**
```json
[
  {"name": "Rudransh Dwivedi", "roll_no": "2023CSE001", "marked_at": "2025-01-15 10:34:22"}
]
```

---

## 📁 Project Structure

```
smart-attendance-system/
├── app.py              # Main Flask application
├── attendance.db       # SQLite database (auto-created)
├── requirements.txt
└── README.md
```

---

## 🔮 Roadmap

- [ ] Firebase Firestore backend (replace SQLite)
- [ ] Email/SMS notification on attendance < 75%
- [ ] CSV/Excel export for faculty
- [ ] Face recognition as backup verification
- [ ] Mobile-first PWA

---

## 🛠️ Tech Stack
**Backend:** Python · Flask · SQLite &nbsp;|&nbsp; **QR:** qrcode · Pillow &nbsp;|&nbsp; **Frontend:** HTML · CSS · Jinja2

---

## 📄 License
MIT License
