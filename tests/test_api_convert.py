"""Tests for the convert endpoint (Issue #5)."""

import io
import pytest
from PIL import Image
import numpy as np
from fastapi.testclient import TestClient

from app.main import api_app
from app.core.security import SignatureManager, InMemorySessionStore


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(api_app)


@pytest.fixture
def signature_manager():
    """Get the signature manager from app state."""
    return api_app.state.signature_manager


@pytest.fixture
def valid_session(signature_manager):
    """Create a valid session and signature."""
    session_id, client_signature = signature_manager.issue_signature(
        client_secret="test-secret"
    )
    return session_id, client_signature


def create_test_image(width: int = 512, height: int = 512, format: str = "PNG") -> bytes:
    """Create a test image in memory."""
    img = Image.new("RGB", (width, height), color=(73, 109, 137))
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)
    return buffer.getvalue()


def test_convert_missing_signature(client):
    """Test convert endpoint without signature returns 401."""
    image_bytes = create_test_image()
    
    response = client.post(
        "/convert",
        files={"file": ("test.png", image_bytes, "image/png")},
        data={"mode": "auto"},
    )
    
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_convert_invalid_mode(client, valid_session):
    """Test convert endpoint with invalid mode returns 400."""
    session_id, client_signature = valid_session
    image_bytes = create_test_image()
    
    response = client.post(
        "/convert",
        files={"file": ("test.png", image_bytes, "image/png")},
        data={"mode": "invalid"},
        headers={
            "X-Session-Id": session_id,
            "X-Client-Signature": client_signature,
        },
    )
    
    assert response.status_code == 422
    assert "Invalid mode" in response.json()["error"]["message"]


def test_convert_prompt_mode_without_prompt(client, valid_session):
    """Test convert endpoint with prompt mode but no prompt returns 400."""
    session_id, client_signature = valid_session
    image_bytes = create_test_image()
    
    response = client.post(
        "/convert",
        files={"file": ("test.png", image_bytes, "image/png")},
        data={"mode": "prompt"},
        headers={
            "X-Session-Id": session_id,
            "X-Client-Signature": client_signature,
        },
    )
    
    assert response.status_code == 422
    assert "prompt field is required" in response.json()["error"]["message"]


def test_convert_file_too_large(client, valid_session):
    """Test convert endpoint with file exceeding size limit returns 413."""
    session_id, client_signature = valid_session
    
    # Create a large image (simulate > 10MB)
    large_image = b"x" * (11 * 1024 * 1024)
    
    response = client.post(
        "/convert",
        files={"file": ("test.png", large_image, "image/png")},
        data={"mode": "auto"},
        headers={
            "X-Session-Id": session_id,
            "X-Client-Signature": client_signature,
        },
    )
    
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_convert_unsupported_format(client, valid_session):
    """Test convert endpoint with unsupported format returns 415."""
    session_id, client_signature = valid_session
    
    # Create a BMP image (not supported)
    img = Image.new("RGB", (512, 512), color=(73, 109, 137))
    buffer = io.BytesIO()
    img.save(buffer, format="BMP")
    buffer.seek(0)
    bmp_bytes = buffer.getvalue()
    
    response = client.post(
        "/convert",
        files={"file": ("test.bmp", bmp_bytes, "image/bmp")},
        data={"mode": "auto"},
        headers={
            "X-Session-Id": session_id,
            "X-Client-Signature": client_signature,
        },
    )
    
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_convert_success_auto_mode(client, valid_session):
    """Test successful conversion with auto mode."""
    session_id, client_signature = valid_session
    image_bytes = create_test_image()
    
    response = client.post(
        "/convert",
        files={"file": ("test.png", image_bytes, "image/png")},
        data={"mode": "auto", "return_previews": "false", "return_metadata": "true"},
        headers={
            "X-Session-Id": session_id,
            "X-Client-Signature": client_signature,
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "succeeded"
    assert "job_id" in data
    assert data["psd"]["url"].startswith("/files/")
    assert data["psd"]["layer_count"] == 1
    assert "timing" in data
    assert "total" in data["timing"]
    assert "request_id" in data


def test_convert_success_prompt_mode(client, valid_session):
    """Test successful conversion with prompt mode."""
    session_id, client_signature = valid_session
    image_bytes = create_test_image()
    
    response = client.post(
        "/convert",
        files={"file": ("test.png", image_bytes, "image/png")},
        data={"mode": "prompt", "prompt": "person . table . book"},
        headers={
            "X-Session-Id": session_id,
            "X-Client-Signature": client_signature,
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "succeeded"
    assert "job_id" in data


def test_convert_with_different_formats(client, valid_session):
    """Test conversion with different image formats."""
    session_id, client_signature = valid_session
    
    for fmt in ["PNG", "JPEG"]:
        image_bytes = create_test_image(format=fmt)
        
        response = client.post(
            "/convert",
            files={"file": (f"test.{fmt.lower()}", image_bytes, f"image/{fmt.lower()}")},
            data={"mode": "auto"},
            headers={
                "X-Session-Id": session_id,
                "X-Client-Signature": client_signature,
            },
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "succeeded"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
