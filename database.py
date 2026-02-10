from __future__ import annotations

import sqlite3
import smtplib
from email.mime.text import MIMEText
import os
import pandas as pd
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "health_data.db")


def _get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = _get_conn()

    # --- users table ---
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT
        )
        """
    )

    # Migrate existing users table: drop activation_code/activated columns if present
    col_names = [row[1] for row in conn.execute("PRAGMA table_info(users)")]
    if "activation_code" in col_names or "activated" in col_names:
        conn.execute(
            """
            CREATE TABLE users_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO users_v2 (id, username, email)
            SELECT id, username, email FROM users
            """
        )
        conn.execute("DROP TABLE users")
        conn.execute("ALTER TABLE users_v2 RENAME TO users")
        conn.commit()

    # --- entries table ---
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entries'")
    if cursor.fetchone():
        col_names = [row[1] for row in conn.execute("PRAGMA table_info(entries)")]
        if "user_email" in col_names and "username" not in col_names:
            # Migrate: rename user_email column to username
            conn.execute(
                """
                CREATE TABLE entries_v2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    date TEXT,
                    weight_lbs REAL,
                    calories REAL,
                    UNIQUE(username, date)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO entries_v2 (username, date, weight_lbs, calories)
                SELECT user_email, date, weight_lbs, calories FROM entries
                """
            )
            conn.execute("DROP TABLE entries")
            conn.execute("ALTER TABLE entries_v2 RENAME TO entries")
            conn.commit()
        # else: already has username column or fresh schema — no migration needed
    else:
        conn.execute(
            """
            CREATE TABLE entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                date TEXT,
                weight_lbs REAL,
                calories REAL,
                UNIQUE(username, date)
            )
            """
        )
        conn.commit()

    conn.close()


# ==================== USER FUNCTIONS ====================

def create_user(username: str, email: str | None = None):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO users (username, email) VALUES (?, ?)",
        (username, email),
    )
    conn.commit()
    conn.close()


def get_user(username: str) -> dict | None:
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def username_exists(username: str) -> bool:
    return get_user(username) is not None


def send_username_reminder(to_email: str, username: str):
    try:
        smtp_email = st.secrets["SMTP_EMAIL"]
        smtp_password = st.secrets["SMTP_PASSWORD"]
    except (KeyError, FileNotFoundError):
        return False

    msg = MIMEText(
        f"Hello {username},\n\n"
        f"Your Health Tracker username is: {username}\n\n"
        "Keep this email for your records in case you forget your username.\n"
    )
    msg["Subject"] = "Health Tracker - Your Username"
    msg["From"] = smtp_email
    msg["To"] = to_email

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, to_email, msg.as_string())
    return True


# ==================== ENTRY FUNCTIONS ====================

def save_entry(username: str, date: str, weight: float, calories: float | None):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO entries (username, date, weight_lbs, calories) VALUES (?, ?, ?, ?)",
        (username, date, weight, calories),
    )
    conn.commit()
    conn.close()


def get_all_entries(username: str) -> pd.DataFrame:
    conn = _get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM entries WHERE username = ? ORDER BY date ASC",
        conn,
        params=(username,),
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


def export_csv(filepath: str, username: str):
    df = get_all_entries(username)
    df.to_csv(filepath, index=False)


def import_csv(filepath: str, username: str):
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
            "INSERT OR REPLACE INTO entries (username, date, weight_lbs, calories) VALUES (?, ?, ?, ?)",
            (username, date, weight, calories),
        )
    conn.commit()
    conn.close()
