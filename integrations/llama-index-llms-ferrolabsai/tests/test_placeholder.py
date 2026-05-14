"""Sanity tests for the llama-index-llms-ferrolabsai 0.0.1 placeholder release.

These tests verify that the placeholder package imports cleanly under the
LlamaIndex namespace, exposes the expected version string, and that any
attempt to use the planned public API fails with a clear NotImplementedError
pointing at the roadmap.
"""

from __future__ import annotations

import pytest

from llama_index.llms import ferrolabsai


def test_version_is_placeholder() -> None:
    assert ferrolabsai.__version__ == "0.0.1"


def test_planned_api_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError) as excinfo:
        ferrolabsai.FerroLabsAI
    message = str(excinfo.value)
    assert "FerroLabsAI" in message
    assert "0.0.1" in message
    assert "ferro-labs" in message.lower()


def test_unknown_attribute_raises_attribute_error() -> None:
    with pytest.raises(AttributeError):
        ferrolabsai.NonExistentClass  # type: ignore[attr-defined]
