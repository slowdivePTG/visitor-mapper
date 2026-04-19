# Visitor Map Backend

A lightweight FastAPI backend designed to track website visitors' geolocation and display them on an interactive map. Originally built to provide a dynamic visitor tracking feature for static sites (like GitHub Pages).

## Architecture: Why PostgreSQL over SQLite?

Before pushing this to the cloud, there is one crucial architectural reality of modern free hosting to address: **ephemeral file systems**.

Platforms like Render, Railway, and Heroku spin your application down when it isn't receiving traffic to save resources. When it spins back up, it boots from a fresh slate. If deployed using a local `sqlite3` database file to one of these free tiers, your `visitors.db` file would be completely wiped out every time the server goes to sleep, effectively resetting your map multiple times a day.

To make the map permanent without paying for a persistent cloud disk, the database has been decoupled from the application file system. We use a serverless PostgreSQL database hosted on [Neon.tech](https://neon.tech/) to take advantage of its permanent free tier. This ensures the data lives safely on a separate, permanent server while keeping the entire infrastructure completely free.

## Features

- **FastAPI-powered**: Fast, async-ready API endpoints.
- **Geolocation**: Resolves client IP addresses to geographic coordinates, city, and country.
- **Smart Filtering**: Automatically ignores local development IPs and known bot/datacenter traffic.
- **PostgreSQL Database**: Securely stores visitor data with timestamped entries on a permanent remote server.
- **Interactive Map**: Generates an HTML map of all visitor locations using [Folium](https://python-visualization.github.io/folium/).
- **Modern Tooling**: Managed with `uv` and `pyproject.toml`.

## Endpoints

- `GET /api/track`: Captures the user's IP, fetches their geolocation, and stores it in the database. Returns a JSON status.
- `GET /map`: Queries the database and returns an interactive HTML map visualizing all tracked visitors.

## Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) (recommended for dependency management)

## Database Setup (Neon.tech)

Instead of a local SQLite file, we use a serverless PostgreSQL database to keep the data permanent and the hosting free.

1. Go to [Neon.tech](https://neon.tech/) and create a new project.
2. Find your **Connection String** (it will look something like `postgresql://user:password@hostname/dbname?sslmode=require`).
3. Save this string; you will need it as your `DATABASE_URL` environment variable.

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
   DATABASE_URL="postgresql://user:password@hostname/dbname?sslmode=require"
   ```

3. **Run the server:**
   ```bash
   # If you aren't using python-dotenv, pass the variable inline:
   DATABASE_URL="your_neon_db_url" uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **View the API:**
   - Tracking endpoint: `http://localhost:8000/api/track`
   - Interactive Map: `http://localhost:8000/map`

## Deployment (Render)

This application is ready to be deployed to Render's free tier.

1. Connect your repository to Render.
2. Create a **Web Service** (You do *not* need to create a Render PostgreSQL database, since we are using Neon).
3. **Build Command**: `pip install .`
4. **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Environment Variables**:
   - Add `DATABASE_URL` and set its value to your **Neon.tech connection string**. *(Note: Ensure you do NOT wrap the string in quotation marks `"` inside the Render dashboard).*

## 🤖 Vibe Coding

This project is an exercise in **vibe coding**. The human developer provided the creative direction, architectural constraints (like avoiding ephemeral file systems on free tiers), and overall vibes. 

The implementation, debugging, Git operations, and deployment configurations were autonomously generated and refined by **opencode**, an interactive CLI AI agent. 
