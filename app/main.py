"""
App entry point. Run from the PROYEKT-2 root directory with:
    uvicorn app.main:app --reload
"""

from dotenv import load_dotenv
load_dotenv()  # loads GROQ_API_KEY from .env

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.api import router

app = FastAPI(title="Document Analyzer API")

# Allow the frontend (running on a different port during dev) to call this API.
# Tighten allow_origins to your actual frontend URL before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
