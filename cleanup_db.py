import os
import time
import httpx
import argparse
import ipaddress
from dotenv import load_dotenv

from database import execute as db_execute, executemany as db_executemany, get_db_connection
from services import is_bot_ip

# Load environment variables from .env if present
load_dotenv()

def truncate_database():
    print("🚨 WARNING: Completely clearing the visitors database...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('TRUNCATE TABLE visitors RESTART IDENTITY;')
        conn.commit()
        print("✅ Database cleared successfully!")
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
    finally:
        conn.close()

def clean_bots():
    print("Starting database bot cleanup...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, ip_address FROM visitors")
        records = cursor.fetchall()
        
        if not records:
            print("No records found in the database.")
            return

        ids_to_delete = []

        with httpx.Client() as client:
            for row_id, ip_address in records:
                print(f"Checking IP {ip_address} (ID: {row_id})... ", end="", flush=True)
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
            db_executemany(cursor, "DELETE FROM visitors WHERE id = %s", [(i,) for i in ids_to_delete])
            conn.commit()
            print("✅ Bot cleanup complete!")
        else:
            print("\n✅ No bots found in existing records. Database is clean!")
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
    finally:
        conn.close()

def purge_ip_network(cidr):
    network = ipaddress.ip_network(cidr, strict=False)
    print(f"Purging visitor records in {network}...")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, ip_address FROM visitors")
        records = cursor.fetchall()

        ids_to_delete = []
        for row_id, ip_address in records:
            try:
                parsed_ip = ipaddress.ip_address(ip_address)
            except ValueError:
                continue

            if parsed_ip in network:
                ids_to_delete.append(row_id)

        if not ids_to_delete:
            print(f"No records found in {network}.")
            return 0

        db_executemany(cursor, "DELETE FROM visitors WHERE id = %s", [(i,) for i in ids_to_delete])
        conn.commit()
        print(f"Deleted {len(ids_to_delete)} records from {network}.")
        return len(ids_to_delete)
    except Exception as e:
        conn.rollback()
        print(f"Error purging {network}: {e}")
        raise
    finally:
        conn.close()

def purge_ip_address(ip_address):
    print(f"Purging visitor records for {ip_address}...")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        db_execute(cursor, "DELETE FROM visitors WHERE ip_address = %s", (ip_address,))
        deleted_count = cursor.rowcount
        conn.commit()
        print(f"Deleted {deleted_count} records for {ip_address}.")
        return deleted_count
    except Exception as e:
        conn.rollback()
        print(f"Error purging {ip_address}: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visitor Map Database Cleanup Utility")
    parser.add_argument("--all", action="store_true", help="Completely wipe the database (TRUNCATE TABLE)")
    parser.add_argument("--ip", help="Delete visitor records for one exact IP address")
    parser.add_argument("--cidr", help="Delete visitor records in an IP network, e.g. 205.169.39.0/24")
    args = parser.parse_args()

    if args.cidr:
        purge_ip_network(args.cidr)
    elif args.ip:
        purge_ip_address(args.ip)
    elif args.all:
        # Require confirmation before wiping the production database
        confirm = input("Are you sure you want to completely wipe all visitor data? (y/N): ")
        if confirm.lower() == 'y':
            truncate_database()
        else:
            print("Aborted.")
    else:
        clean_bots()
