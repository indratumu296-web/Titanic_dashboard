import os
import re
import sqlite3
from pathlib import Path

import pandas as pd
import psycopg2

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "Titanic-Dataset.csv"

DB_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": os.getenv("PGPORT", "5432"),
    "dbname": os.getenv("PGDATABASE", "titanic_db"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", ""),
    # Always search the project schema; block any writes.
    "options": "-c search_path=titanic_project,public "
               "-c default_transaction_read_only=on",
}


def _fallback_dataframe():
    """Load a local Titanic sample when Postgres is unavailable."""
    df = pd.read_csv(CSV_PATH)
    df.columns = [str(column).strip().lower() for column in df.columns]
    df = df.rename(
        columns={
            "passengerid": "passengerid",
            "name": "name",
            "sex": "sex",
            "age": "age",
            "pclass": "pclass",
            "fare": "fare",
            "embarked": "embarked",
            "cabin": "cabin",
            "survived": "survived",
        }
    )
    for column in ["passengerid", "pclass", "survived"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)
    for column in ["age", "fare"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def _sqlite_connection():
    """Create an in-memory SQLite database with Titanic data."""
    conn = sqlite3.connect(":memory:")
    df = _fallback_dataframe()
    df.to_sql("passengers", conn, index=False, if_exists="replace")
    df.to_sql("titanic_staging", conn, index=False, if_exists="replace")
    conn.row_factory = sqlite3.Row
    return conn


def _rewrite_sqlite_query(sql, params):
    """Translate a PostgreSQL-style query to SQLite-compatible SQL."""
    rewritten = sql

    for cast_type in ("text", "numeric", "int", "integer", "float", "double", "real"):
        rewritten = rewritten.replace(f"::{cast_type}", "")

    if params is not None:
        param_values = list(params)
        if len(param_values) > 0 and all(
            isinstance(value, (list, tuple, set)) for value in param_values
        ):
            def replace_any(match):
                values = list(param_values.pop(0))
                return "IN (" + ", ".join("?" for _ in values) + ")"

            rewritten = re.sub(
                r"=\s*ANY\(\s*%s\s*\)",
                replace_any,
                rewritten,
                flags=re.IGNORECASE,
            )
            flat_params = []
            for value in params:
                flat_params.extend(list(value))
            params = flat_params

    return rewritten, params


def run_query(sql, params=None):
    """Execute a read-only query and return a DataFrame."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                columns = [c[0] for c in cur.description]
                rows = cur.fetchall()
            return pd.DataFrame(rows, columns=columns)
        finally:
            conn.close()
    except Exception:
        sqlite_conn = _sqlite_connection()
        try:
            sqlite_sql, sqlite_params = _rewrite_sqlite_query(sql, params)
            sqlite_params = () if sqlite_params is None else sqlite_params
            cursor = sqlite_conn.execute(sqlite_sql, sqlite_params)
            rows = cursor.fetchall()
            columns = [column[0] for column in cursor.description]
            return pd.DataFrame(rows, columns=columns)
        finally:
            sqlite_conn.close()