"""Package version helpers."""

from __future__ import annotations

try:
    from importlib.metadata import version

    __version__ = version("ferrolabsai")
except Exception:
    __version__ = "0.2.0"
