"""
Module de base de données pour AgentGuard.
Stocke les sessions, les étapes (trace), les alertes déclenchées par les
règles, et les jugements rendus par le juge IA.

Deux moteurs possibles, choisis automatiquement :
- PostgreSQL si la variable d'environnement DATABASE_URL est définie
  (production : les données survivent aux redéploiements et aux mises en veille) ;
- SQLite sinon (développement local, rien à installer).
"""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agentguard.db")

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

# Seule différence de schéma entre les deux moteurs : la clé auto-incrémentée.
_AUTO_ID = "SERIAL PRIMARY KEY" if USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_request TEXT,
        started_at TEXT,
        status TEXT DEFAULT 'en_cours'
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS steps (
        id {_AUTO_ID},
        session_id TEXT,
        step_number INTEGER,
        reasoning TEXT,
        tool_called TEXT,
        tool_params TEXT,
        tool_result TEXT,
        timestamp TEXT
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS alerts (
        id {_AUTO_ID},
        session_id TEXT,
        step_number INTEGER,
        rule_triggered TEXT,
        severity TEXT,
        created_at TEXT
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS judgments (
        id {_AUTO_ID},
        session_id TEXT,
        anomalie_detectee INTEGER,
        raison TEXT,
        gravite TEXT,
        action_recommandee TEXT,
        created_at TEXT
    )
    """,
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _cursor():
    """Ouvre une connexion, valide (commit) si tout va bien, puis la ferme."""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=15)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _sql(query: str) -> str:
    """Les requêtes sont écrites avec '?' (SQLite) ; Postgres attend '%s'."""
    return query.replace("?", "%s") if USE_POSTGRES else query


def _execute(query: str, params: tuple = ()) -> None:
    with _cursor() as cur:
        cur.execute(_sql(query), params)


def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    with _cursor() as cur:
        cur.execute(_sql(query), params)
        return [dict(row) for row in cur.fetchall()]


def init_db():
    with _cursor() as cur:
        for statement in _SCHEMA:
            cur.execute(statement)


def create_session(user_request: str) -> str:
    session_id = str(uuid.uuid4())
    _execute(
        "INSERT INTO sessions (id, user_request, started_at, status) VALUES (?, ?, ?, ?)",
        (session_id, user_request, _now(), "en_cours"),
    )
    return session_id


def log_step(session_id: str, step: dict):
    _execute(
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
            _now(),
        ),
    )


def log_alert(session_id: str, step_number: int, rule_triggered: str, severity: str):
    _execute(
        """INSERT INTO alerts (session_id, step_number, rule_triggered, severity, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (session_id, step_number, rule_triggered, severity, _now()),
    )


def log_judgment(session_id: str, judgment: dict):
    _execute(
        """INSERT INTO judgments
           (session_id, anomalie_detectee, raison, gravite, action_recommandee, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            1 if judgment.get("anomalie_detectee") else 0,
            judgment.get("raison"),
            judgment.get("gravite"),
            judgment.get("action_recommandee"),
            _now(),
        ),
    )


def update_session_status(session_id: str, status: str):
    _execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))


def get_sessions(limit: int = 50):
    return _fetch_all("SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,))


def get_session_detail(session_id: str):
    sessions = _fetch_all("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if not sessions:
        return None
    return {
        "session": sessions[0],
        "steps": _fetch_all(
            "SELECT * FROM steps WHERE session_id = ? ORDER BY step_number", (session_id,)
        ),
        "alerts": _fetch_all(
            "SELECT * FROM alerts WHERE session_id = ? ORDER BY step_number", (session_id,)
        ),
        "judgments": _fetch_all(
            "SELECT * FROM judgments WHERE session_id = ? ORDER BY id", (session_id,)
        ),
    }