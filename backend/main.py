# backend/main.py
"""Uvicorn entrypoint. Run via: uvicorn main:app --reload"""

from api.server import create_app

app = create_app()
