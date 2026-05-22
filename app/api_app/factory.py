from fastapi import FastAPI
from app.core.config import settings


def build_api_app() -> FastAPI:
    """Build and configure the API FastAPI application."""
    app = FastAPI(title="API App", version="1.0.0")
    
    @app.get("/health")
    def health_check():
        """Health check endpoint for API app."""
        return {"status": "ok", "service": "api_app"}
    
    return app
