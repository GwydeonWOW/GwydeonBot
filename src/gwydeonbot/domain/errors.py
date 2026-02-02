class WowApiError(Exception):
    """Base exception for API/client errors."""


class WowNotFound(WowApiError):
    """Resource not found (404)."""


class WowRateLimited(WowApiError):
    """Rate limit from a remote API (429)."""
