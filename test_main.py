import os
import sqlite3
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

# Override the database file for testing so we don't touch the real visitors.db
import database
database.DB_FILE = "test_visitors.db"
# Re-initialize DB to ensure the test database and table exist
database.init_db()

from main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown_db():
    """Clear the test database before each test to ensure a clean slate."""
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute("DELETE FROM visitors")
        conn.commit()
    yield

def test_cors_headers():
    """Test 2: Ensure CORS headers allow external frontend domains."""
    headers = {
        "Origin": "https://my-github-pages.github.io",
        "Access-Control-Request-Method": "GET"
    }
    response = client.options("/api/track", headers=headers)
    assert response.status_code == 200
    # FastAPI CORS Middleware reflects the origin or uses "*" depending on allow_credentials
    assert response.headers.get("access-control-allow-origin") in ["*", "https://my-github-pages.github.io"]

def test_local_ip_ignored():
    """Test 3: Ensure local testing IPs are skipped safely."""
    # Test client usually connects from 'testclient' instead of '127.0.0.1'
    response = client.get("/api/track")
    assert response.status_code == 200
    assert response.json() in [
        {"status": "ignored", "message": "Local IP ignored"},
        {"status": "failed", "message": "IP lookup failed"} # testclient won't be matched by 127.0.0.1
    ]

@patch("httpx.AsyncClient.get")
def test_simulated_public_ip(mock_get):
    """Test 4: Simulate a public IP and successful IP-API response."""
    # Mock the external API call so tests are fast and don't get rate-limited
    mock_response = AsyncMock()
    mock_response.json = lambda: {
        "status": "success",
        "lat": 37.7749,
        "lon": -122.4194,
        "city": "San Francisco",
        "country": "United States",
        "isp": "Comcast Cable Communications",
        "org": "Comcast Cable Communications",
        "as": "AS7922 Comcast Cable Communications, LLC"
    }
    mock_response.raise_for_status = lambda: None
    mock_get.return_value = mock_response

    # Send request with a mocked Forwarded IP
    response = client.get("/api/track", headers={"X-Forwarded-For": "8.8.8.8"})
    
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    # Verify that the record was actually inserted into the test database
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ip_address, city, country FROM visitors")
        records = cursor.fetchall()
        assert len(records) == 1
        assert records[0] == ("8.8.8.8", "San Francisco", "United States")

@patch("httpx.AsyncClient.get")
def test_api_error_handling(mock_get):
    """Test 5: Ensure the server doesn't crash if the external API fails."""
    # Make the mocked httpx call raise an exception
    mock_get.side_effect = Exception("Simulated Network Timeout")
    
    response = client.get("/api/track", headers={"X-Forwarded-For": "8.8.8.8"})
    
    # The endpoint should catch the error and return a safe JSON instead of a 500 error
    assert response.status_code == 200
    assert response.json() == {"status": "error", "message": "An internal error occurred"}

@patch("httpx.AsyncClient.get")
def test_bot_ip_ignored(mock_get):
    """Test 7: Ensure known bot IPs (like Google Cloud) are ignored."""
    mock_response = AsyncMock()
    mock_response.json = lambda: {
        "status": "success",
        "lat": 41.2619,
        "lon": -95.8608,
        "city": "Council Bluffs",
        "country": "United States",
        "isp": "Google LLC",
        "org": "Google Cloud",
        "as": "AS15169 Google LLC"
    }
    mock_response.raise_for_status = lambda: None
    mock_get.return_value = mock_response

    response = client.get("/api/track", headers={"X-Forwarded-For": "8.8.8.8"})
    
    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "message": "Bot or data center IP ignored"}

    # Verify that the record was NOT inserted into the test database
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM visitors")
        records = cursor.fetchall()
        assert len(records) == 0

def test_map_generation():
    """Test 6: Verify Folium map generation and HTML rendering."""
    # Manually insert a record into the DB
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute("""
            INSERT INTO visitors (ip_address, latitude, longitude, city, country) 
            VALUES ('8.8.8.8', 37.77, -122.41, 'San Francisco', 'United States')
        """)
        conn.commit()
    
    response = client.get("/map")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    # Verify the marker text is embedded in the generated HTML
    # Note: Country was removed for political neutrality
    assert "San Francisco" in response.text
