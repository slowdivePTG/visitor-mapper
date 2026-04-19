# Visitor Map Backend

A lightweight FastAPI backend designed to track website visitors' geolocation and display them on an interactive map. Originally built to provide a dynamic visitor tracking feature for static sites (like GitHub Pages).

## Features

- **FastAPI-powered**: Fast, async-ready API endpoints.
- **Geolocation**: Resolves client IP addresses to geographic coordinates, city, and country.
- **Smart Filtering**: Automatically ignores local development IPs and known bot/datacenter traffic.
- **PostgreSQL Database**: Securely stores visitor data with timestamped entries.
- **Interactive Map**: Generates an HTML map of all visitor locations using [Folium](https://python-visualization.github.io/folium/).
- **Modern Tooling**: Managed with `uv` and `pyproject.toml`.

## Endpoints

- `GET /api/track`: Captures the user's IP, fetches their geolocation, and stores it in the database. Returns a JSON status.
- `GET /map`: Queries the database and returns an interactive HTML map visualizing all tracked visitors.

## Prerequisites

- Python 3.8+
- PostgreSQL database
- [uv](https://github.com/astral-sh/uv) (recommended for dependency management)

## Local Development Setup

1. **Install dependencies:**
   ```bash
   uv sync
   # or
   pip install -e .
   ```

2. **Database Configuration:**
   The application requires a PostgreSQL connection string. Set the `DATABASE_URL` environment variable.
   
   If using `.env` (requires `uv add python-dotenv`):
   ```env
   DATABASE_URL="postgresql://username:password@localhost:5432/visitor_map_db"
   ```

3. **Run the server:**
   ```bash
   # If you aren't using python-dotenv, pass the variable inline:
   DATABASE_URL="your_db_url" uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **View the API:**
   - Tracking endpoint: `http://localhost:8000/api/track`
   - Interactive Map: `http://localhost:8000/map`

## Deployment (Render)

This application is ready to be deployed to platforms like Render.

1. Connect your repository to Render.
2. Create a **Web Service** and a **PostgreSQL Database**.
3. **Build Command**: (Render uses standard pip by default, but supports `pyproject.toml` directly, or you can configure `uv`).
4. **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Environment Variables**:
   - Add `DATABASE_URL` and set its value to your Render PostgreSQL internal connection string.
