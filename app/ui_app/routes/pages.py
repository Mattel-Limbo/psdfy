"""UI pages routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

router = APIRouter(tags=["ui-pages"])


def get_template_path(filename: str) -> Path:
    """Get template file path from project root."""
    # Get project root (3 levels up from this file)
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / "web" / "templates" / filename


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
