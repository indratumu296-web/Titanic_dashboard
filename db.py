import os
import re
import sqlite3
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "Titanic-Dataset.csv"
load_dotenv(BASE_DIR / ".env")

DB_CONFIG = {
    "host": os.getenv("SUPABASE_HOST", ""),
    "port": os.getenv("SUPABASE_PORT", "5432"),
    "dbname": os.getenv("SUPABASE_DBNAME", "postgres"),
    "user": os.getenv("SUPABASE_USER", "postgres"),
    "password": os.getenv("SUPABASE_DB_PASSWORD", ""),
    "sslmode": "require",
    "connect_timeout": int(os.getenv("SUPABASE_CONNECT_TIMEOUT", "10")),
}


def _load_local_data():
    df = pd.read_csv(CSV_PATH)
    df.columns = [str(col).strip().lower() for col in df.columns]
    for col in ["passengerid", "pclass", "survived"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in ["age", "fare"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _sqlite_connection():
    conn = sqlite3.connect(":memory:")
    df = _load_local_data()
    df.to_sql("passengers", conn, index=False, if_exists="replace")
    df.to_sql("titanic_staging", conn, index=False, if_exists="replace")
    conn.row_factory = sqlite3.Row
    return conn


def _rewrite_sqlite_query(sql, params):
    rewritten = sql
    for cast_type in ("text", "numeric", "int", "integer", "float", "double", "real"):
        rewritten = rewritten.replace(f"::{cast_type}", "")

    if params is not None:
        param_values = list(params)
        if param_values and all(isinstance(v, (list, tuple, set)) for v in param_values):
            def replace_any(match):
                values = list(param_values.pop(0))
                return "IN (" + ", ".join("?" for _ in values) + ")"

            rewritten = re.sub(r"=\s*ANY\(\s*%s\s*\)", replace_any, rewritten, flags=re.IGNORECASE)
            flat = []
            for value in params:
                flat.extend(list(value))
            params = flat

    return rewritten, params


def run_query(sql, params=None):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cur:
                if params is None:
                    cur.execute(sql)
                else:
                    cur.execute(sql, params)
                if cur.description is None:
                    return pd.DataFrame()
                columns = [col[0] for col in cur.description]
                rows = cur.fetchall()
            return pd.DataFrame(rows, columns=columns)
        finally:
            conn.close()
    except psycopg2.OperationalError:
        sqlite_conn = _sqlite_connection()
        try:
            sqlite_sql, sqlite_params = _rewrite_sqlite_query(sql, params)
            if sqlite_params is None:
                sqlite_params = ()
            cursor = sqlite_conn.execute(sqlite_sql, sqlite_params)
            rows = cursor.fetchall()
            columns = [c[0] for c in cursor.description]
            return pd.DataFrame(rows, columns=columns)
        finally:
            sqlite_conn.close()