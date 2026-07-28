import datetime
import psycopg2
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from database import get_db_connection, execute as db_execute
from services import get_client_ip, fetch_geolocation, is_filtered_ip, is_bot_ip, is_bot_ua, is_bot_webdriver
from map_render import generate_globe_map

router = APIRouter()

# 3. The Tracking Endpoint
@router.get("/api/track")
async def track_visitor(request: Request):
    ip_address = get_client_ip(request)
    
    # Avoid tracking local dev IPs
    if ip_address in ("127.0.0.1", "::1", "localhost", "testclient"):
        return JSONResponse({"status": "ignored", "message": "Local IP ignored"})

    if is_filtered_ip(ip_address):
        return JSONResponse({"status": "ignored", "message": "Filtered IP range"})

    # Check client-side webdriver signal (cheap, no network call)
    webdriver_val = request.query_params.get("wd")
    if is_bot_webdriver(webdriver_val):
        return JSONResponse({"status": "ignored", "message": "Bot webdriver signal detected"})

    try:
        # Check User-Agent first (cheap, no network call)
        user_agent = request.headers.get("user-agent", "")
        if is_bot_ua(user_agent):
            return JSONResponse({"status": "ignored", "message": "Bot User-Agent ignored"})

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
                
                # Check if this IP was already tracked in the last 6 hours
                db_execute(cursor, """
                    SELECT id FROM visitors 
                    WHERE ip_address = %s 
                    AND timestamp > NOW() - INTERVAL '6 hours'
                    LIMIT 1
                """, (ip_address,))
                
                if cursor.fetchone():
                    return JSONResponse({"status": "ignored", "message": "IP recently tracked"})

                # Collect additional browser/client signals
                referrer = request.headers.get("referer", "") or request.query_params.get("ref", "")
                page_url = request.query_params.get("path", "")
                language = request.query_params.get("lang", "")
                try:
                    screen_width = int(request.query_params.get("sw"))
                except (TypeError, ValueError):
                    screen_width = None
                try:
                    screen_height = int(request.query_params.get("sh"))
                except (TypeError, ValueError):
                    screen_height = None

                # If not tracked recently, insert them!
                db_execute(cursor, """
                    INSERT INTO visitors
                        (ip_address, latitude, longitude, city, country, timestamp,
                         user_agent, referrer, webdriver, screen_width, screen_height, language, page_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    ip_address,
                    geo_data.get("lat"),
                    geo_data.get("lon"),
                    geo_data.get("city"),
                    geo_data.get("country"),
                    datetime.datetime.now(datetime.timezone.utc),
                    user_agent or None,
                    referrer or None,
                    True if webdriver_val == "1" else (False if webdriver_val == "0" else None),
                    screen_width,
                    screen_height,
                    language or None,
                    page_url or None,
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

    # Generate Globe map HTML
    map_html = generate_globe_map(records)

    # Return the map's HTML representation directly
    return HTMLResponse(content=map_html)
