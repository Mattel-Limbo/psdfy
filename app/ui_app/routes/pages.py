"""UI pages routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

router = APIRouter(tags=["ui-pages"])


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve home page."""
    # Read app.html template
    template_path = os.path.join(
        os.path.dirname(__file__),
        "../../web/templates/app.html"
    )
    
    try:
        with open(template_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>App page not found</h1>"


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve login page."""
    # Read login.html template
    template_path = os.path.join(
        os.path.dirname(__file__),
        "../../web/templates/login.html"
    )
    
    try:
        with open(template_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Login page not found</h1>"
