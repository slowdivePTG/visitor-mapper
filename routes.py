import datetime
import os
import psycopg2
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from database import get_db_connection
from services import get_client_ip, fetch_geolocation, is_bot_ip
from map_render import generate_folium_map

router = APIRouter()

# 3. The Tracking Endpoint
@router.get("/api/track")
async def track_visitor(request: Request):
    ip_address = get_client_ip(request)
    
    # Avoid tracking local dev IPs
    if ip_address in ("127.0.0.1", "::1", "localhost", "testclient"):
        return JSONResponse({"status": "ignored", "message": "Local IP ignored"})

    try:
        # Fetch geolocation data using the service function
        geo_data = await fetch_geolocation(ip_address)

        # Only store if the API successfully found the location
        if geo_data.get("status") == "success":
            # Filter out known bots and data centers
            if is_bot_ip(geo_data):
                return JSONResponse({"status": "ignored", "message": "Bot or data center IP ignored"})

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO visitors (ip_address, latitude, longitude, city, country, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    ip_address,
                    geo_data.get("lat"),
                    geo_data.get("lon"),
                    geo_data.get("city"),
                    geo_data.get("country"),
                    datetime.datetime.now(datetime.timezone.utc)
                ))
                conn.commit()
            finally:
                conn.close()
            return JSONResponse({"status": "success"})
        else:
            return JSONResponse({"status": "failed", "message": "IP lookup failed"})

    except Exception as e:
        # Catch all exceptions so the endpoint never crashes the frontend
        print(f"Tracking error: {e}")
        return JSONResponse({"status": "error", "message": "An internal error occurred"})

# 4. The Map Endpoint
@router.get("/map", response_class=HTMLResponse)
async def get_map():
    # Query database for all visitors, ordered by newest first
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT latitude, longitude, city, country, timestamp FROM visitors ORDER BY timestamp DESC")
        records = cursor.fetchall()
    finally:
        conn.close()

    # Generate Folium map HTML
    map_html = generate_folium_map(records)

    # Return the map's HTML representation directly
    return HTMLResponse(content=map_html)
