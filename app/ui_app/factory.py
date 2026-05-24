from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.core.config import settings
from app.ui_app.routes import pages, auth, proxy


def build_ui_app() -> FastAPI:
    """Build and configure the UI FastAPI application."""
    app = FastAPI(title="UI App", version="1.0.0")
    
    @app.get("/health")
    def health_check():
        """Health check endpoint for UI app."""
        return {"status": "ok", "service": "ui_app"}
    
    # Include routers
    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(proxy.router)
    
    # Mount static files if they exist
    static_dir = Path(__file__).parent.parent.parent / "web" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    return app
