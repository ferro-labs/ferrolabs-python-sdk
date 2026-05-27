"""Tests for the legacy FerroLLM completion-style adapter."""

from __future__ import annotations

import json

from pytest_httpx import HTTPXMock

from langchain_ferrolabsai import FerroLLM

from .conftest import BASE_URL, make_chat_completion


def _build(**overrides) -> FerroLLM:
    kwargs = {"model": "gpt-4o", "base_url": BASE_URL, "api_key": "sk-ferro-test"}
    kwargs.update(overrides)
    return FerroLLM(**kwargs)  # type: ignore[arg-type]


def test_invoke_returns_string(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/v1/chat/completions",
        json=make_chat_completion(content="hello world"),
    )
    llm = _build()
    assert llm.invoke("hi") == "hello world"


def test_wraps_prompt_in_single_user_message(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/v1/chat/completions",
        json=make_chat_completion(),
    )
    llm = _build()
    llm.invoke("ping")
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["messages"] == [{"role": "user", "content": "ping"}]


def test_llm_type():
    assert _build()._llm_type == "ferro-labs"


def test_forwards_temperature_and_max_tokens(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/v1/chat/completions",
        json=make_chat_completion(),
    )
    llm = _build(temperature=0.7, max_tokens=128)
    llm.invoke("hi")
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["temperature"] == 0.7
    assert body["max_tokens"] == 128
