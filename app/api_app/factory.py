from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid

from app.core.config import settings
from app.core.security import SignatureManager, InMemorySessionStore
from app.core.errors import AppError
from app.middleware.client_signature import ClientSignatureMiddleware
from app.api_app.routes import auth, convert


def build_api_app() -> FastAPI:
    """Build and configure the API FastAPI application."""
    app = FastAPI(
        title="Psdfy API",
        version="1.0.0",
        description="Image to PSD conversion API with client signature authentication",
    )
    
    # Initialize signature manager with in-memory store
    session_store = InMemorySessionStore()
    signature_manager = SignatureManager(
        store=session_store,
        ttl_seconds=settings.SIGNATURE_TTL_SECONDS,
        timestamp_skew=settings.SIGNATURE_TIMESTAMP_SKEW,
        pepper=settings.SIGNATURE_SECRET_PEPPER,
        salt_length=settings.SIGNATURE_SALT_LENGTH,
    )
    
    # Store in app state for dependency injection
    app.state.signature_manager = signature_manager
    app.state.session_store = session_store
    
    # Add CORS middleware
    origins = settings.CORS_ALLOWED_ORIGINS.split(",") if settings.CORS_ALLOWED_ORIGINS != "*" else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add client signature verification middleware
    app.add_middleware(
        ClientSignatureMiddleware,
        signature_manager=signature_manager,
        protected_paths=["/convert", "/files"],
    )
    
    # Global exception handler for AppError
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": request_id,
                }
            },
        )
    
    # Health check endpoint (public)
    @app.get("/health")
    def health_check():
        """Health check endpoint for API app."""
        return {"status": "ok", "service": "api_app"}
    
    @app.get("/version")
    def version():
        """Get version information."""
        return {"version": "1.0.0", "service": "api_app"}
    
    # Dependency injection for signature manager
    async def get_signature_manager():
        return app.state.signature_manager
    
    # Include routers
    app.include_router(auth.router)
    app.include_router(convert.router)
    
    return app
