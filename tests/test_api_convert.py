"""Tests for the convert endpoint (Issue #5)."""

import io
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from PIL import Image
from fastapi.testclient import TestClient

from app.main import api_app
from app.core.security import SignatureManager, InMemorySessionStore
from app.api_app.routes.convert import _get_capabilities
from app.schemas.mask import Mask
from app.utils.geometry import calculate_bbox


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
    import time
    import uuid
    client_secret = str(uuid.uuid4())
    client_ts = str(int(time.time()))
    result = signature_manager.issue(client_secret=client_secret, client_ts=client_ts)
    return result["sessionId"], result["clientSignature"]


@pytest.fixture
def capabilities():
    """Get current model capabilities."""
    return _get_capabilities()


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


def _make_mock_segmenter(image_shape=(512, 512)):
    """Return a mock Segmenter that produces one rectangular mask without loading any model."""
    h, w = image_shape[:2]
    mask_array = np.zeros((h, w), dtype=np.bool_)
    mask_array[50:450, 50:450] = True
    bbox = {"top": 50, "left": 50, "bottom": 450, "right": 450}
    fake_mask = Mask(mask=mask_array, bbox=bbox, area=int(mask_array.sum()), score=0.9, label="object_0")

    mock_seg = MagicMock()
    mock_seg.segment_auto.return_value = [fake_mask]
    mock_seg.segment_with_prompt.return_value = [fake_mask]
    return mock_seg


@pytest.mark.skipif(
    "auto" not in _get_capabilities()["modes"],
    reason="SAM 2 not installed — auto mode unavailable",
)
def test_convert_success_auto_mode(client, valid_session):
    """Test successful conversion with auto mode (segmenter mocked)."""
    session_id, client_signature = valid_session
    image_bytes = create_test_image()

    with patch("app.api_app.routes.convert.get_segmenter", return_value=_make_mock_segmenter()):
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
    assert "/files/" in data["psd"]["url"]
    assert data["psd"]["layer_count"] >= 1
    assert "timing" in data
    assert "total" in data["timing"]
    assert "request_id" in data


def test_convert_success_prompt_mode(client, valid_session):
    """Test successful conversion with prompt mode (segmenter mocked)."""
    session_id, client_signature = valid_session
    image_bytes = create_test_image()

    with patch("app.api_app.routes.convert.get_segmenter", return_value=_make_mock_segmenter()):
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


def test_convert_with_different_formats(client, valid_session, capabilities):
    """Test conversion with different image formats using the default available mode (segmenter mocked)."""
    session_id, client_signature = valid_session
    default_mode = capabilities["default_mode"]

    if default_mode is None:
        pytest.skip("No segmentation models available")

    extra = {"prompt": "object"} if default_mode == "prompt" else {}

    with patch("app.api_app.routes.convert.get_segmenter", return_value=_make_mock_segmenter()):
        for fmt in ["PNG", "JPEG"]:
            image_bytes = create_test_image(format=fmt)

            response = client.post(
                "/convert",
                files={"file": (f"test.{fmt.lower()}", image_bytes, f"image/{fmt.lower()}")},
                data={"mode": default_mode, **extra},
                headers={
                    "X-Session-Id": session_id,
                    "X-Client-Signature": client_signature,
                },
            )

            assert response.status_code == 200
            assert response.json()["status"] == "succeeded"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
