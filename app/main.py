from app.api_app.factory import build_api_app
from app.ui_app.factory import build_ui_app

# Build both applications
api_app = build_api_app()
ui_app = build_ui_app()

__all__ = ["api_app", "ui_app"]
