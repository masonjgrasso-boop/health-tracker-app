from __future__ import annotations

import sqlite3
import os
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "health_data.db")


def _get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = _get_conn()
    # Migrate: if old `entries` table exists without user_email, create new schema
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entries'")
    if cursor.fetchone():
        col_names = [row[1] for row in conn.execute("PRAGMA table_info(entries)")]
        if "user_email" not in col_names:
            conn.execute(
                """
                CREATE TABLE entries_v2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_email TEXT NOT NULL,
                    date TEXT,
                    weight_lbs REAL,
                    calories REAL,
                    UNIQUE(user_email, date)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO entries_v2 (user_email, date, weight_lbs, calories)
                SELECT 'unknown', date, weight_lbs, calories FROM entries
                """
            )
            conn.execute("DROP TABLE entries")
            conn.execute("ALTER TABLE entries_v2 RENAME TO entries")
            conn.commit()
    else:
        conn.execute(
            """
            CREATE TABLE entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                date TEXT,
                weight_lbs REAL,
                calories REAL,
                UNIQUE(user_email, date)
            )
            """
        )
        conn.commit()
    conn.close()


def save_entry(user_email: str, date: str, weight: float, calories: float | None):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO entries (user_email, date, weight_lbs, calories) VALUES (?, ?, ?, ?)",
        (user_email, date, weight, calories),
    )
    conn.commit()
    conn.close()


def get_all_entries(user_email: str) -> pd.DataFrame:
    conn = _get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM entries WHERE user_email = ? ORDER BY date ASC",
        conn,
        params=(user_email,),
        parse_dates=["date"],
    )
    conn.close()
    return df


def delete_entry(entry_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def update_entry(entry_id: int, date: str, weight: float, calories: float | None):
    conn = _get_conn()
    conn.execute(
        "UPDATE entries SET date = ?, weight_lbs = ?, calories = ? WHERE id = ?",
        (date, weight, calories, entry_id),
    )
    conn.commit()
    conn.close()


def export_csv(filepath: str, user_email: str):
    df = get_all_entries(user_email)
    df.to_csv(filepath, index=False)


def import_csv(filepath: str, user_email: str):
    df = pd.read_csv(filepath)
    conn = _get_conn()
    for _, row in df.iterrows():
        weight = row.get("weight_lbs")
        calories = row.get("calories")
        date = str(row.get("date", ""))
        if pd.isna(weight):
            weight = None
        if pd.isna(calories):
            calories = None
        conn.execute(
            "INSERT OR REPLACE INTO entries (user_email, date, weight_lbs, calories) VALUES (?, ?, ?, ?)",
            (user_email, date, weight, calories),
        )
    conn.commit()
    conn.close()
