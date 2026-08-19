"""FastAPI application entry point.

Wires together `core` (engine/datasets/scenarios - framework-agnostic) with
HTML pages and a JSON API. `core` never imports anything from `app`, so the
engine/datasets/scenarios stay reusable by other future Blue Team Simulator
modules that don't want a web frontend at all.

Run from the repo root (inside the venv):
    uvicorn app.main:app --reload
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import api, pages

APP_DIR = Path(__file__).parent

app = FastAPI(title="Blue Team Simulator - KQL")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.include_router(pages.router)
app.include_router(api.router)
