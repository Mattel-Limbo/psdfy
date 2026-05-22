from fastapi import FastAPI
from app.core.config import settings


def build_ui_app() -> FastAPI:
    """Build and configure the UI FastAPI application."""
    app = FastAPI(title="UI App", version="1.0.0")
    
    @app.get("/health")
    def health_check():
        """Health check endpoint for UI app."""
        return {"status": "ok", "service": "ui_app"}
    
    return app
