
import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "student_assistant.db"


def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sb_profile (
                id INTEGER PRIMARY KEY,
                profile_json TEXT NOT NULL,
                updated_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sb_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT NOT NULL,
                subject TEXT NOT NULL,
                duration REAL NOT NULL,
                status TEXT DEFAULT 'Pending'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sb_chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sb_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                subject TEXT NOT NULL,
                content TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)


def save_profile(profile):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO sb_profile
            (id, profile_json, updated_at)
            VALUES (1, ?, ?)
        """, (
            json.dumps(profile, ensure_ascii=False),
            datetime.now().isoformat()
        ))


def load_profile():
    with get_connection() as conn:
        row = conn.execute("""
            SELECT profile_json
            FROM sb_profile
            WHERE id = 1
        """).fetchone()

    if not row:
        return None

    try:
        return json.loads(row[0])
    except (ValueError, TypeError):
        return None


def save_sessions(sessions):
    with get_connection() as conn:
        conn.execute("DELETE FROM sb_sessions")

        for item in sessions:
            conn.execute("""
                INSERT INTO sb_sessions
                (session_date, subject, duration, status)
                VALUES (?, ?, ?, ?)
            """, (
                item["date"],
                item["subject"],
                float(item["duration"]),
                item.get("status", "Pending")
            ))


def load_sessions():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT session_date, subject, duration, status
            FROM sb_sessions
            ORDER BY session_date, id
        """).fetchall()

    return [
        {
            "date": row[0],
            "subject": row[1],
            "duration": row[2],
            "status": row[3]
        }
        for row in rows
    ]


def save_chat(role, message):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO sb_chat (role, message, created_at)
            VALUES (?, ?, ?)
        """, (
            role,
            message,
            datetime.now().isoformat()
        ))


def load_chat(limit=40):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT role, message
            FROM (
                SELECT id, role, message
                FROM sb_chat
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
        """, (limit,)).fetchall()

    return rows


def clear_chat():
    with get_connection() as conn:
        conn.execute("DELETE FROM sb_chat")


def save_material(filename, subject, content):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO sb_materials
            (filename, subject, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            filename,
            subject,
            content,
            datetime.now().isoformat()
        ))


def load_materials():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, filename, subject, content
            FROM sb_materials
            ORDER BY id DESC
        """).fetchall()

    return rows


def delete_material(material_id):
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM sb_materials
            WHERE id = ?
        """, (material_id,))


# Create database tables when this module is imported.
init_database()
