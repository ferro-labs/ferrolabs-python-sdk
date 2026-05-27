"""FerroLLM — legacy completion-style LangChain ``LLM`` for the Ferro gateway.

Most new code should use :class:`langchain_ferrolabsai.FerroChatModel` instead.
``FerroLLM`` exists for chains still built on the legacy ``LLM`` interface and
internally wraps the gateway's chat-completions endpoint with a single user
message.
"""

from __future__ import annotations

from typing import Any

from ferrolabsai import FerroClient
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import LLM
from pydantic import ConfigDict, Field, PrivateAttr, SecretStr


class FerroLLM(LLM):
    """Legacy completion-style adapter — wraps chat completions with a single user message."""

    model: str = Field(...)
    base_url: str | None = None
    api_key: SecretStr | None = None
    timeout: float = 120.0
    max_retries: int = 2
    temperature: float | None = None
    max_tokens: int | None = None
    route_tag: str | None = None
    default_headers: dict[str, str] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    _client_instance: FerroClient | None = PrivateAttr(default=None)

    @property
    def _llm_type(self) -> str:
        return "ferro-labs"

    def _get_client(self) -> FerroClient:
        if self._client_instance is None:
            self._client_instance = FerroClient(
                api_key=self.api_key.get_secret_value() if self.api_key else None,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
                default_headers=self.default_headers,
            )
        return self._client_instance

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> str:
        params: dict[str, Any] = {"model": self.model}
        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        if stop is not None:
            params["stop"] = stop
        if self.route_tag is not None:
            params["route_tag"] = self.route_tag
        params.update(kwargs)

        response = self._get_client().chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            **params,
        )
        return response.content or ""
