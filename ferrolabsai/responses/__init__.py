"""Responses API resources (``/v1/responses``)."""

from .async_resource import AsyncResponses
from .resource import Responses

__all__ = ["AsyncResponses", "Responses"]
