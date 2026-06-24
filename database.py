import sqlite3
import datetime
import psycopg2
import os

# Register adapter for Python 3.12+ SQLite datetime handling
sqlite3.register_adapter(datetime.datetime, lambda dt: dt.isoformat())

DB_FILE = "visitors.db"

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)
    return sqlite3.connect(DB_FILE)

def _is_sqlite(conn):
    return isinstance(conn, sqlite3.Connection)

def _adapt_query(query, is_sqlite):
    if not is_sqlite:
        return query
    query = query.replace("%s", "?")
    query = query.replace("NOW() - INTERVAL '6 hours'", "datetime('now', '-6 hours')")
    return query

def execute(cursor, query, params=None):
    is_sqlite = _is_sqlite(cursor.connection)
    query = _adapt_query(query, is_sqlite)
    if params is not None:
        cursor.execute(query, params)
    else:
        cursor.execute(query)

def executemany(cursor, query, params_list):
    is_sqlite = _is_sqlite(cursor.connection)
    query = _adapt_query(query, is_sqlite)
    cursor.executemany(query, params_list)

def init_db():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        is_sqlite = _is_sqlite(conn)

        if is_sqlite:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS visitors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT,
                    latitude REAL,
                    longitude REAL,
                    city TEXT,
                    country TEXT,
                    timestamp TIMESTAMP
                )
            """)
            cursor.execute("PRAGMA table_info(visitors)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            for col_name, col_type in [
                ("user_agent", "TEXT"),
                ("referrer", "TEXT"),
                ("webdriver", "INTEGER"),
                ("screen_width", "INTEGER"),
                ("screen_height", "INTEGER"),
                ("language", "TEXT"),
                ("page_url", "TEXT"),
            ]:
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE visitors ADD COLUMN {col_name} {col_type}")
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS visitors (
                    id SERIAL PRIMARY KEY,
                    ip_address TEXT,
                    latitude REAL,
                    longitude REAL,
                    city TEXT,
                    country TEXT,
                    timestamp TIMESTAMP
                )
            """)
            cursor.execute("""
                ALTER TABLE visitors
                    ADD COLUMN IF NOT EXISTS user_agent TEXT,
                    ADD COLUMN IF NOT EXISTS referrer TEXT,
                    ADD COLUMN IF NOT EXISTS webdriver BOOLEAN,
                    ADD COLUMN IF NOT EXISTS screen_width INTEGER,
                    ADD COLUMN IF NOT EXISTS screen_height INTEGER,
                    ADD COLUMN IF NOT EXISTS language TEXT,
                    ADD COLUMN IF NOT EXISTS page_url TEXT
            """)
        conn.commit()
    finally:
        conn.close()
