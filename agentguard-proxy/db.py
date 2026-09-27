"""
Module de base de données pour AgentGuard.
Stocke les sessions, les étapes (trace), les alertes déclenchées par les
règles, et les jugements rendus par le juge IA.
"""

import sqlite3
import json
import os
import uuid
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "agentguard.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_request TEXT,
            started_at TEXT,
            status TEXT DEFAULT 'en_cours'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            step_number INTEGER,
            reasoning TEXT,
            tool_called TEXT,
            tool_params TEXT,
            tool_result TEXT,
            timestamp TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            step_number INTEGER,
            rule_triggered TEXT,
            severity TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS judgments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            anomalie_detectee INTEGER,
            raison TEXT,
            gravite TEXT,
            action_recommandee TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def create_session(user_request: str) -> str:
    session_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (id, user_request, started_at, status) VALUES (?, ?, ?, ?)",
        (session_id, user_request, datetime.now(timezone.utc).isoformat(), "en_cours"),
    )
    conn.commit()
    conn.close()
    return session_id


def log_step(session_id: str, step: dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO steps
           (session_id, step_number, reasoning, tool_called, tool_params, tool_result, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            step.get("step"),
            step.get("reasoning"),
            step.get("tool_called"),
            json.dumps(step.get("tool_params")) if step.get("tool_params") else None,
            json.dumps(step.get("tool_result")) if step.get("tool_result") else None,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def log_alert(session_id: str, step_number: int, rule_triggered: str, severity: str):
    conn = get_connection()
    conn.execute(
        """INSERT INTO alerts (session_id, step_number, rule_triggered, severity, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (session_id, step_number, rule_triggered, severity, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def log_judgment(session_id: str, judgment: dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO judgments
           (session_id, anomalie_detectee, raison, gravite, action_recommandee, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            1 if judgment.get("anomalie_detectee") else 0,
            judgment.get("raison"),
            judgment.get("gravite"),
            judgment.get("action_recommandee"),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def update_session_status(session_id: str, status: str):
    conn = get_connection()
    conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))
    conn.commit()
    conn.close()


def get_sessions(limit: int = 50):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_detail(session_id: str):
    conn = get_connection()
    session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    steps = conn.execute(
        "SELECT * FROM steps WHERE session_id = ? ORDER BY step_number", (session_id,)
    ).fetchall()
    alerts = conn.execute(
        "SELECT * FROM alerts WHERE session_id = ? ORDER BY step_number", (session_id,)
    ).fetchall()
    judgments = conn.execute(
        "SELECT * FROM judgments WHERE session_id = ?", (session_id,)
    ).fetchall()
    conn.close()
    if not session:
        return None
    return {
        "session": dict(session),
        "steps": [dict(s) for s in steps],
        "alerts": [dict(a) for a in alerts],
        "judgments": [dict(j) for j in judgments],
    }