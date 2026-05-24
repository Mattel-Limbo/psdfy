from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.core.config import settings
from app.core.errors import AppError, UnauthorizedError
from app.ui_app.routes import pages, auth, proxy
from app.middleware.ui_session import UISessionMiddleware


def build_ui_app() -> FastAPI:
    """Build and configure the UI FastAPI application."""
    app = FastAPI(title="UI App", version="1.0.0")
    
    # Add UI session middleware (must be added before routes)
    app.add_middleware(UISessionMiddleware)
    
    @app.get("/health")
    def health_check():
        """Health check endpoint for UI app."""
        return {"status": "ok", "service": "ui_app"}
    
    # Global exception handler for UnauthorizedError
    @app.exception_handler(UnauthorizedError)
    async def unauthorized_error_handler(request: Request, exc: UnauthorizedError):
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "unauthorized",
                    "message": str(exc),
                }
            },
        )
    
    # Global exception handler for AppError
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )
    
    # Include routers
    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(proxy.router)
    
    # Mount static files if they exist
    static_dir = Path(__file__).parent.parent.parent / "web" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    return app
