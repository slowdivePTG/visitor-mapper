from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import database
from routes import router

app = FastAPI(title="Visitor Tracker")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Initialization
database.init_db()

# Include all tracked routes
app.include_router(router)
