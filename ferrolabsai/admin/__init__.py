"""Admin API resources — manage the OSS gateway via /admin/*."""

from .async_resource import AsyncAdmin
from .resource import Admin

__all__ = ["Admin", "AsyncAdmin"]
