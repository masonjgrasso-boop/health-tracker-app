import sqlite3
import os
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "health_data.db")


def _get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            weight_lbs REAL,
            calories REAL
        )
        """
    )
    conn.commit()
    conn.close()


def save_entry(date: str, weight: float, calories: float | None):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO entries (date, weight_lbs, calories) VALUES (?, ?, ?)",
        (date, weight, calories),
    )
    conn.commit()
    conn.close()


def get_all_entries() -> pd.DataFrame:
    conn = _get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM entries ORDER BY date ASC", conn, parse_dates=["date"]
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


def export_csv(filepath: str):
    df = get_all_entries()
    df.to_csv(filepath, index=False)


def import_csv(filepath: str):
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
            "INSERT OR REPLACE INTO entries (date, weight_lbs, calories) VALUES (?, ?, ?)",
            (date, weight, calories),
        )
    conn.commit()
    conn.close()
