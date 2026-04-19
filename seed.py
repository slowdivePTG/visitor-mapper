import os
import datetime
import random
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

from database import get_db_connection

# Mock cities with varying visitor weights to test the logarithmic scaling
cities = [
    {"city": "Chicago", "country": "United States", "lat": 41.8781, "lon": -87.6298, "weight": 45}, # Max size dot
    {"city": "London", "country": "United Kingdom", "lat": 51.5074, "lon": -0.1278, "weight": 12},  # Medium dot
    {"city": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503, "weight": 4},           # Small-ish dot
    {"city": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522, "weight": 2},            # Small dot
]

def seed_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        now = datetime.datetime.now(datetime.timezone.utc)
        records = []
        
        # 1. Insert historical visitors based on weights
        for city_data in cities:
            for _ in range(city_data["weight"]):
                # Randomize past timestamps (1 to 30 days ago)
                ts = now - datetime.timedelta(minutes=random.randint(10, 40000))
                records.append((
                    f"192.168.1.{random.randint(1, 255)}", # Fake IP
                    city_data["lat"],
                    city_data["lon"],
                    city_data["city"],
                    city_data["country"],
                    ts
                ))
        
        # 2. Insert a CURRENT visitor (Most recent timestamp)
        # We will put the current visitor in Sydney!
        records.append((
            "10.0.0.1",
            -33.8688,
            151.2093,
            "Sydney",
            "Australia",
            now # Exact current time makes it the "Current Visitor"
        ))

        cursor.executemany("""
            INSERT INTO visitors (ip_address, latitude, longitude, city, country, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, records)
        
        conn.commit()
        conn.close()
        print(f"✅ Successfully seeded {len(records)} mock visitors into the database!")
        print("🌍 You can now view the scaling dots at http://localhost:8000/map")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        print("Make sure you have a .env file with your DATABASE_URL set up locally!")

if __name__ == "__main__":
    seed_db()
