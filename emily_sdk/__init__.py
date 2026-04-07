"""
EMILY SDK — Python client for the EMILY incident management API.

Provides a high-level interface for creating, importing, and exporting incidents,
with built-in support for resumable batch uploads.
"""

from emily_sdk.client import EmilyClient
from emily_sdk.exceptions import EmilyError, AuthError, ValidationError, APIError
from emily_sdk.tracker import UploadTracker

__version__ = "0.1.0"

__all__ = [
    "EmilyClient",
    "EmilyError",
    "AuthError",
    "ValidationError",
    "APIError",
    "UploadTracker",
]
