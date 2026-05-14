"""Sanity tests for the langchain-ferrolabsai 0.0.1 placeholder release.

These tests verify that the placeholder package imports cleanly, exposes the
expected version string, and that any attempt to use the planned public API
fails with a clear NotImplementedError pointing at the roadmap.
"""

from __future__ import annotations

import pytest

import langchain_ferrolabsai


def test_version_is_placeholder() -> None:
    assert langchain_ferrolabsai.__version__ == "0.0.1"


@pytest.mark.parametrize("name", ["FerroChatModel", "FerroEmbeddings", "FerroLLM"])
def test_planned_api_raises_not_implemented(name: str) -> None:
    with pytest.raises(NotImplementedError) as excinfo:
        getattr(langchain_ferrolabsai, name)
    message = str(excinfo.value)
    assert name in message
    assert "0.0.1" in message
    assert "ferro-labs" in message.lower()


def test_unknown_attribute_raises_attribute_error() -> None:
    with pytest.raises(AttributeError):
        langchain_ferrolabsai.NonExistentClass  # type: ignore[attr-defined]
