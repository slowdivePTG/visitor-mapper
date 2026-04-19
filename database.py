import psycopg2
import os

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    return psycopg2.connect(db_url)

def init_db():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
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
        conn.commit()
    finally:
        conn.close()
