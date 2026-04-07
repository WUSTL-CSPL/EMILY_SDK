"""Custom exceptions for the EMILY SDK."""


class EmilyError(Exception):
    """Base exception for all SDK errors."""
    pass


class AuthError(EmilyError):
    """Raised when authentication fails (401)."""
    pass


class ValidationError(EmilyError):
    """Raised when input data fails client-side validation."""
    pass


class APIError(EmilyError):
    """Raised when the API returns an error response."""

    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
