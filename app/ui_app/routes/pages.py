"""UI pages routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pathlib import Path
import os
import sys

router = APIRouter(tags=["ui-pages"])


def get_template_path(filename: str) -> Path:
    """Get template file path - works both in dev and installed package."""
    # Try multiple locations
    possible_paths = [
        # Development: relative to this file (app/web/templates)
        # From app/ui_app/routes/pages.py -> go up 3 levels to app, then web/templates
        Path(__file__).parent.parent.parent / "web" / "templates" / filename,
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    # Return first path as fallback (for error message)
    return possible_paths[0]


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve home page."""
    template_path = get_template_path("app.html")
    
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"<h1>App page not found at {template_path}</h1>"


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve login page."""
    template_path = get_template_path("login.html")
    
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"<h1>Login page not found at {template_path}</h1>"
