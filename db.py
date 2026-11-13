import os
import re
import sqlite3
from pathlib import Path

import pandas as pd

try:
    import psycopg2
except ModuleNotFoundError:
    psycopg2 = None

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "Titanic-Dataset.csv"


def _load_env_file():
    env_path = BASE_DIR / ".env"
    if not env_path.is_file():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)


_load_env_file()

DB_CONFIG = {
    "host": os.getenv("SUPABASE_HOST", " db.psbvvwvtrvfwzhqyzwix.supabase.co"),
    "port": os.getenv("SUPABASE_PORT", "5432"),
    "dbname": os.getenv("SUPABASE_DBNAME", "postgres"),
    "user": os.getenv("SUPABASE_USER", "postgres"),
    "password": os.getenv("SUPABASE_DB_PASSWORD", "Indra@296!jd"),
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
    password = DB_CONFIG["password"]
    if (
        psycopg2 is None
        or not DB_CONFIG["host"]
        or not password
        or password == "replace_with_your_supabase_database_password"
    ):
        return _run_sqlite_query(sql, params)

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
        return _run_sqlite_query(sql, params)


def _run_sqlite_query(sql, params):
    sqlite_conn = _sqlite_connection()
    try:
        sqlite_sql, sqlite_params = _rewrite_sqlite_query(sql, params)
        if sqlite_params is None:
            sqlite_params = ()
        cursor = sqlite_conn.execute(sqlite_sql, sqlite_params)
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        return pd.DataFrame(rows, columns=columns)
    finally:
        sqlite_conn.close()