"""Custom exception classes for the application."""


class AppError(Exception):
    """Base exception for all application errors."""
    
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InvalidImageError(AppError):
    """Raised when image is invalid, corrupted, or unsupported."""
    
    def __init__(self, message: str):
        super().__init__("INVALID_IMAGE", message, 422)


class FileTooLargeError(AppError):
    """Raised when uploaded file exceeds size limit."""
    
    def __init__(self, message: str):
        super().__init__("FILE_TOO_LARGE", message, 413)


class UnsupportedMediaTypeError(AppError):
    """Raised when file type is not supported."""
    
    def __init__(self, message: str):
        super().__init__("UNSUPPORTED_MEDIA_TYPE", message, 415)


class UnauthorizedError(AppError):
    """Raised when authentication fails (missing/invalid credentials)."""
    
    def __init__(self, message: str = "Missing or invalid credentials"):
        super().__init__("UNAUTHORIZED", message, 401)


class SignatureExpiredError(AppError):
    """Raised when signature or session has expired."""
    
    def __init__(self, message: str = "Signature or session expired"):
        super().__init__("SIGNATURE_EXPIRED", message, 403)


class SignatureRevokedError(AppError):
    """Raised when signature or session has been revoked."""
    
    def __init__(self, message: str = "Signature or session revoked"):
        super().__init__("SIGNATURE_REVOKED", message, 403)


class SegmentationError(AppError):
    """Raised when segmentation model fails."""
    
    def __init__(self, message: str):
        super().__init__("SEGMENTATION_ERROR", message, 500)


class PSDWriteError(AppError):
    """Raised when PSD writing fails."""
    
    def __init__(self, message: str):
        super().__init__("PSD_WRITE_ERROR", message, 500)


class ModelNotReadyError(AppError):
    """Raised when model is warming up or GPU is busy."""
    
    def __init__(self, message: str = "Model is warming up or GPU is busy"):
        super().__init__("MODEL_NOT_READY", message, 503)
