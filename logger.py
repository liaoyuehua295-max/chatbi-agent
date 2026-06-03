import sqlite3
import os
from datetime import datetime

LOG_DB = os.path.join(os.path.dirname(__file__), "logs.db")

def init_db():
    conn = sqlite3.connect(LOG_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            user_name TEXT DEFAULT '匿名',
            question TEXT,
            sql TEXT,
            answer TEXT,
            row_count INTEGER,
            has_chart INTEGER,
            has_error INTEGER,
            error_msg TEXT,
            insight TEXT,
            feedback INTEGER DEFAULT 0,
            feedback_note TEXT
        )
    """)
    # 兼容旧表：尝试加user_name列（已存在则忽略）
    try:
        conn.execute("ALTER TABLE query_logs ADD COLUMN user_name TEXT DEFAULT '匿名'")
    except Exception:
        pass
    conn.commit()
    conn.close()

def log_query(question, sql, answer, row_count, has_chart,
              error_msg=None, insight=None, user_name="匿名") -> int:
    init_db()
    conn = sqlite3.connect(LOG_DB)
    cur = conn.execute("""
        INSERT INTO query_logs
        (created_at, user_name, question, sql, answer, row_count, has_chart, has_error, error_msg, insight)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user_name,
        question, sql, answer,
        row_count if row_count is not None else -1,
        1 if has_chart else 0,
        1 if error_msg else 0,
        error_msg or "",
        insight or "",
    ))
    log_id = cur.lastrowid
    conn.commit()
    conn.close()
    return log_id

def update_feedback(log_id: int, feedback: int, note: str = ""):
    conn = sqlite3.connect(LOG_DB)
    conn.execute(
        "UPDATE query_logs SET feedback=?, feedback_note=? WHERE id=?",
        (feedback, note, log_id)
    )
    conn.commit()
    conn.close()

def get_all_logs(limit=500):
    init_db()
    conn = sqlite3.connect(LOG_DB)
    import pandas as pd
    df = pd.read_sql_query(
        "SELECT * FROM query_logs ORDER BY id DESC LIMIT ?",
        conn, params=(limit,)
    )
    conn.close()
    return df
