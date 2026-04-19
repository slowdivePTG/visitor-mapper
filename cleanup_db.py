import sqlite3
import httpx
import time
from services import is_bot_ip
import database

def clean_database():
    print("Starting database cleanup...")
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, ip_address FROM visitors")
        records = cursor.fetchall()
        
    ids_to_delete = []

    with httpx.Client() as client:
        for row_id, ip_address in records:
            print(f"Checking IP {ip_address} (ID: {row_id})... ", end="")
            try:
                response = client.get(f"http://ip-api.com/json/{ip_address}")
                response.raise_for_status()
                geo_data = response.json()
                
                if is_bot_ip(geo_data):
                    print("Identified as BOT. Marking for deletion.")
                    ids_to_delete.append(row_id)
                else:
                    print("Clean.")
                
            except Exception as e:
                print(f"Error fetching data: {e}")
            
            # Sleep to respect rate limits of free ip-api tier
            time.sleep(1.5)

    if ids_to_delete:
        print(f"\nDeleting {len(ids_to_delete)} bot records...")
        with sqlite3.connect(database.DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.executemany("DELETE FROM visitors WHERE id = ?", [(i,) for i in ids_to_delete])
            conn.commit()
        print("Cleanup complete!")
    else:
        print("\nNo bots found in existing records. Database is clean!")

if __name__ == "__main__":
    clean_database()
