import os
import sqlite3
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

os.environ["DATABASE_URL"] = ""

import database
database.DB_FILE = "test_visitors.db"
database.init_db()

from main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown_db():
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute("DELETE FROM visitors")
        conn.commit()
    yield

def test_cors_headers():
    headers = {
        "Origin": "https://my-github-pages.github.io",
        "Access-Control-Request-Method": "GET"
    }
    response = client.options("/api/track", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in ["*", "https://my-github-pages.github.io"]

def test_local_ip_ignored():
    response = client.get("/api/track")
    assert response.status_code == 200
    assert response.json() in [
        {"status": "ignored", "message": "Local IP ignored"},
        {"status": "failed", "message": "IP lookup failed"}
    ]

def test_webdriver_bot_rejected():
    response = client.get("/api/track?wd=1", headers={"X-Forwarded-For": "8.8.8.8"})
    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "message": "Bot webdriver signal detected"}

    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM visitors")
        records = cursor.fetchall()
        assert len(records) == 0

@patch("httpx.AsyncClient.get")
def test_blocked_ip_subnet_ignored(mock_get):
    response = client.get("/api/track", headers={"X-Forwarded-For": "205.169.39.18"})
    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "message": "Blocked IP range"}
    mock_get.assert_not_called()

    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM visitors")
        records = cursor.fetchall()
        assert len(records) == 0

@patch("httpx.AsyncClient.get")
def test_blocked_ip_subnet_similar_ip_ignored(mock_get):
    response = client.get("/api/track", headers={"X-Forwarded-For": "205.169.39.99"})
    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "message": "Blocked IP range"}
    mock_get.assert_not_called()

    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM visitors")
        records = cursor.fetchall()
        assert len(records) == 0

@patch("httpx.AsyncClient.get")
def test_simulated_public_ip(mock_get):
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

    response = client.get(
        "/api/track?wd=0&sw=1920&sh=1080&lang=en-US&path=/research/&ref=https://google.com",
        headers={
            "X-Forwarded-For": "8.8.8.8",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://google.com",
        }
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ip_address, city, country, user_agent, referrer, webdriver, screen_width, screen_height, language, page_url FROM visitors")
        records = cursor.fetchall()
        assert len(records) == 1
        row = records[0]
        assert row[0] == "8.8.8.8"
        assert row[1] == "San Francisco"
        assert row[2] == "United States"
        assert "Mozilla/5.0" in row[3]
        assert row[4] == "https://google.com"
        assert row[5] == 0
        assert row[6] == 1920
        assert row[7] == 1080
        assert row[8] == "en-US"
        assert row[9] == "/research/"

@patch("httpx.AsyncClient.get")
def test_simulated_public_ip_no_params(mock_get):
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

    response = client.get("/api/track", headers={"X-Forwarded-For": "8.8.8.8"})

    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ip_address, user_agent, referrer, webdriver, screen_width, screen_height, language, page_url FROM visitors")
        records = cursor.fetchall()
        assert len(records) == 1
        row = records[0]
        assert row[0] == "8.8.8.8"
        assert row[2] is None or row[2] == ""
        assert row[3] is None or row[3] == 0
        assert row[4] is None
        assert row[5] is None
        assert row[6] is None or row[6] == ""
        assert row[7] is None or row[7] == ""

@patch("httpx.AsyncClient.get")
def test_api_error_handling(mock_get):
    mock_get.side_effect = Exception("Simulated Network Timeout")

    response = client.get("/api/track", headers={"X-Forwarded-For": "8.8.8.8"})

    assert response.status_code == 200
    assert response.json() == {"status": "error", "message": "An internal error occurred"}

@patch("httpx.AsyncClient.get")
def test_bot_ip_ignored(mock_get):
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

    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM visitors")
        records = cursor.fetchall()
        assert len(records) == 0

@patch("httpx.AsyncClient.get")
def test_meta_bot_ignored(mock_get):
    mock_response = AsyncMock()
    mock_response.json = lambda: {
        "status": "success",
        "lat": 33.6500,
        "lon": -83.6800,
        "city": "Social Circle",
        "country": "United States",
        "isp": "Facebook, Inc.",
        "org": "Meta Platforms",
        "as": "AS32934 Facebook, Inc."
    }
    mock_response.raise_for_status = lambda: None
    mock_get.return_value = mock_response

    response = client.get("/api/track", headers={"X-Forwarded-For": "10.0.0.1"})

    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "message": "Bot or data center IP ignored"}

    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM visitors")
        records = cursor.fetchall()
        assert len(records) == 0

def test_map_generation():
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute("""
            INSERT INTO visitors (ip_address, latitude, longitude, city, country)
            VALUES ('8.8.8.8', 37.77, -122.41, 'San Francisco', 'United States')
        """)
        conn.commit()

    response = client.get("/map")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "San Francisco" in response.text
