"""Python SDK for the Baalebos AI gateway: BaalebosAI (sync) and AsyncBaalebosAI (async)."""
from __future__ import annotations

import asyncio
import os
import time
from typing import List, Optional

import httpx
import requests

from . import auth
from .auth import DEFAULT_API_URL
from .exceptions import (
    BaalebosAPIError,
    BaalebosAuthError,
    BaalebosConfigError,
    BaalebosConnectionError,
    BaalebosRateLimitError,
    BaalebosRequestError,
    BaalebosStructuredOutputError,
    BaalebosUnavailableError,
    describe_network_error,
)
from .structured import build_structured_prompt, parse_structured_response

_RETRY_STATUSES = (502, 503, 504)
_sleep = time.sleep  # indirection so tests don't actually wait
_async_sleep = asyncio.sleep


# --------------------------------------------------------------------------------------
# Helpers shared by the sync and async clients (no I/O in here)
# --------------------------------------------------------------------------------------
def derive_url(api_url: str, suffix: str) -> str:
    """'.../webhook/baalebos-ai' + 'signup' -> '.../webhook/baalebos-ai-signup'.
    Lets self-hosted gateways work with no extra configuration."""
    return api_url.rstrip("/") + "-" + suffix


def _resolve_url(api_url: Optional[str]) -> str:
    url = api_url or os.getenv("BAALEBOS_API_URL") or DEFAULT_API_URL
    if not url.startswith(("http://", "https://")):
        raise BaalebosConfigError(f"BAALEBOS_API_URL must start with http:// or https:// (got {url!r}).")
    return url


def _payload(prompt, mode, temperature, model, models) -> dict:
    payload: dict = {"message": prompt, "mode": mode}
    if temperature is not None:
        payload["temperature"] = temperature
    if model:
        payload["model"] = model
    if models:
        payload["models"] = models
    return payload


def _message_from(data, text: str) -> str:
    if isinstance(data, dict):
        found = data.get("message") or data.get("error")
        if found:
            return str(found)
    return (text or "")[:200]


def _raise_for_status(status: int, message: str, api_url: str) -> None:
    if status == 401:
        raise BaalebosAuthError(
            "The gateway rejected your API key. Unset BAALEBOS_API_KEY to use an auto-registered "
            "key, or check the key you supplied.",
            status_code=401,
        )
    if status == 429:
        raise BaalebosRateLimitError(message or "Daily request limit reached; it resets at 00:00 UTC.", 429)
    if status in (400, 413, 422):
        raise BaalebosRequestError(message or f"The gateway rejected the request (HTTP {status}).", status)
    if status == 404:
        raise BaalebosUnavailableError(
            f"Gateway endpoint not found (HTTP 404) at {api_url}. The service may be down, "
            f"or BAALEBOS_API_URL may be wrong.",
            404,
        )
    if status >= 500:
        raise BaalebosUnavailableError(message or f"The gateway is temporarily unavailable (HTTP {status}).", status)
    raise BaalebosAPIError(f"Unexpected response from the gateway (HTTP {status}): {message}", status)


def _extract_text(data) -> str:
    """Understands every shape the gateway has used: text, output, and the nested OpenAI-style
    data.choices[0].message.content."""
    if isinstance(data, dict):
        text = data.get("text") or data.get("output")
        if text:
            return text
        nested = data.get("data")
        choices = nested.get("choices") if isinstance(nested, dict) else None
        if choices:
            try:
                return choices[0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                pass
    raise BaalebosAPIError("The gateway answered but returned no text.", status_code=200)


def _json_or_none(resp):
    try:
        return resp.json()
    except ValueError:
        return None


def _parse_success(resp) -> dict:
    data = _json_or_none(resp)
    if not isinstance(data, dict):
        raise BaalebosUnavailableError("The gateway returned a non-JSON response.", status_code=resp.status_code)
    return data


def _check_json_attempts(max_attempts: int) -> int:
    return max(1, max_attempts)


# --------------------------------------------------------------------------------------
# Health check (no key needed)
# --------------------------------------------------------------------------------------
def _health_url(api_url: Optional[str]) -> str:
    return derive_url(_resolve_url(api_url), "health")


def check_status(api_url: Optional[str] = None, timeout: float = 10.0) -> dict:
    """GET the gateway's health endpoint. Needs no API key."""
    url = _health_url(api_url)
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise BaalebosConnectionError(f"Could not reach the gateway ({url}): {describe_network_error(exc)}") from exc
    if resp.status_code != 200:
        raise BaalebosUnavailableError(f"Health check failed with HTTP {resp.status_code} ({url}).", resp.status_code)
    return _json_or_none(resp) or {"status": "ok"}


# --------------------------------------------------------------------------------------
# Synchronous client
# --------------------------------------------------------------------------------------
class BaalebosAI:
    """
    Synchronous client.

    >>> client = BaalebosAI()            # no key needed: one is registered on first use
    >>> client.chat("explain recursion in one sentence")
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        self.api_url = _resolve_url(api_url)
        self.timeout = timeout
        self.max_retries = max_retries
        self._api_key = api_key or os.getenv("BAALEBOS_API_KEY") or None
        # A key we registered ourselves can be replaced automatically if the gateway stops
        # recognising it (e.g. after a database rebuild). A key you supplied is never swapped.
        self._managed_key = self._api_key is None

    @property
    def api_key(self) -> str:
        if self._api_key is None:
            self._api_key = auth.get_api_key(derive_url(self.api_url, "signup"))
        return self._api_key

    def _reregister(self) -> None:
        auth.forget_saved_key()
        key = auth.register(derive_url(self.api_url, "signup"))
        auth.save_key(key)
        self._api_key = key

    def _post(self, payload: dict) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            if attempt:
                _sleep(0.5 * 2 ** (attempt - 1))
            try:
                resp = requests.post(
                    self.api_url,
                    json=payload,
                    headers={"Content-Type": "application/json", "x-api-key": self.api_key},
                    timeout=self.timeout,
                )
            except requests.ConnectionError as exc:  # includes ConnectTimeout: never reached the server
                last_exc = exc
                continue
            except requests.Timeout as exc:
                # The request may have been processed (and counted); don't replay it.
                raise BaalebosConnectionError(
                    f"Request to {self.api_url} timed out after {self.timeout:g}s."
                ) from exc
            if resp.status_code in _RETRY_STATUSES and attempt < self.max_retries:
                continue
            return resp
        raise BaalebosConnectionError(
            f"Could not reach the gateway at {self.api_url}: {describe_network_error(last_exc)}"
        ) from last_exc

    def chat_raw(
        self,
        prompt: str,
        mode: str = "auto",
        temperature: Optional[float] = 0.7,
        *,
        model: Optional[str] = None,
        models: Optional[List[str]] = None,
    ) -> dict:
        """The gateway's full response: text, usedModel, provider, routingSummary, ..."""
        payload = _payload(prompt, mode, temperature, model, models)
        resp = self._post(payload)
        if resp.status_code == 401 and self._managed_key:
            self._reregister()
            resp = self._post(payload)
        if resp.status_code != 200:
            _raise_for_status(resp.status_code, _message_from(_json_or_none(resp), resp.text), self.api_url)
        return _parse_success(resp)

    def chat(
        self,
        prompt: str,
        mode: str = "auto",
        temperature: Optional[float] = 0.7,
        *,
        model: Optional[str] = None,
        models: Optional[List[str]] = None,
    ) -> str:
        """Prompt in, answer text out."""
        return _extract_text(self.chat_raw(prompt, mode, temperature, model=model, models=models))

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        required_keys: Optional[List[str]] = None,
        mode: str = "auto",
        max_attempts: int = 2,
        temperature: Optional[float] = 0.2,
    ) -> dict:
        """
        Ask for a JSON object and get a dict back.

        The gateway has no system-prompt field, so your instructions are folded into the prompt and
        the answer is parsed leniently. If it still can't be parsed it is asked again, up to
        max_attempts times in total (another provider may answer next time). Raises
        BaalebosStructuredOutputError if it never yields an object with all required_keys.
        """
        prompt = build_structured_prompt(system_prompt, user_prompt)
        last: Optional[BaalebosStructuredOutputError] = None
        for _ in range(_check_json_attempts(max_attempts)):
            try:
                return parse_structured_response(self.chat(prompt, mode, temperature), required_keys)
            except BaalebosStructuredOutputError as exc:
                last = exc
        assert last is not None
        raise last

    def status(self) -> dict:
        return check_status(self.api_url, timeout=min(self.timeout, 10.0))


# --------------------------------------------------------------------------------------
# Asynchronous client
# --------------------------------------------------------------------------------------
class AsyncBaalebosAI:
    """
    Async client for asyncio codebases (FastAPI, scripts...). Same methods, behaviour and error
    types as BaalebosAI, just awaitable.

    Note: `api_key` is None until the first request when no key was supplied, because registering
    a key needs the network and a constructor can't await.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        *,
        _transport: Optional[httpx.AsyncBaseTransport] = None,  # tests inject a mock transport
    ):
        self.api_url = _resolve_url(api_url)
        self.timeout = timeout
        self.max_retries = max_retries
        self._transport = _transport
        self._api_key = api_key or os.getenv("BAALEBOS_API_KEY") or None
        self._managed_key = self._api_key is None

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    async def _ensure_key(self) -> str:
        if self._api_key is None:
            signup = derive_url(self.api_url, "signup")
            # auth.get_api_key does blocking file and network I/O; keep it off the event loop
            self._api_key = await asyncio.get_running_loop().run_in_executor(None, auth.get_api_key, signup)
        return self._api_key

    async def _reregister(self) -> None:
        signup = derive_url(self.api_url, "signup")

        def swap() -> str:
            auth.forget_saved_key()
            key = auth.register(signup)
            auth.save_key(key)
            return key

        self._api_key = await asyncio.get_running_loop().run_in_executor(None, swap)

    async def _post(self, payload: dict) -> httpx.Response:
        last_exc: Optional[Exception] = None
        key = await self._ensure_key()
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as http:
            for attempt in range(self.max_retries + 1):
                if attempt:
                    await _async_sleep(0.5 * 2 ** (attempt - 1))
                try:
                    resp = await http.post(
                        self.api_url,
                        json=payload,
                        headers={"Content-Type": "application/json", "x-api-key": self._api_key or key},
                    )
                except (httpx.ConnectError, httpx.ConnectTimeout) as exc:  # never reached the server
                    last_exc = exc
                    continue
                except httpx.TimeoutException as exc:
                    raise BaalebosConnectionError(
                        f"Request to {self.api_url} timed out after {self.timeout:g}s."
                    ) from exc
                except httpx.TransportError as exc:
                    raise BaalebosConnectionError(
                        f"Could not reach the gateway at {self.api_url}: {describe_network_error(exc)}"
                    ) from exc
                if resp.status_code in _RETRY_STATUSES and attempt < self.max_retries:
                    continue
                return resp
        raise BaalebosConnectionError(
            f"Could not reach the gateway at {self.api_url}: {describe_network_error(last_exc)}"
        ) from last_exc

    async def chat_raw(
        self,
        prompt: str,
        mode: str = "auto",
        temperature: Optional[float] = 0.7,
        *,
        model: Optional[str] = None,
        models: Optional[List[str]] = None,
    ) -> dict:
        payload = _payload(prompt, mode, temperature, model, models)
        resp = await self._post(payload)
        if resp.status_code == 401 and self._managed_key:
            await self._reregister()
            resp = await self._post(payload)
        if resp.status_code != 200:
            _raise_for_status(resp.status_code, _message_from(_json_or_none(resp), resp.text), self.api_url)
        return _parse_success(resp)

    async def chat(
        self,
        prompt: str,
        mode: str = "auto",
        temperature: Optional[float] = 0.7,
        *,
        model: Optional[str] = None,
        models: Optional[List[str]] = None,
    ) -> str:
        return _extract_text(await self.chat_raw(prompt, mode, temperature, model=model, models=models))

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        required_keys: Optional[List[str]] = None,
        mode: str = "auto",
        max_attempts: int = 2,
        temperature: Optional[float] = 0.2,
    ) -> dict:
        prompt = build_structured_prompt(system_prompt, user_prompt)
        last: Optional[BaalebosStructuredOutputError] = None
        for _ in range(_check_json_attempts(max_attempts)):
            try:
                return parse_structured_response(await self.chat(prompt, mode, temperature), required_keys)
            except BaalebosStructuredOutputError as exc:
                last = exc
        assert last is not None
        raise last

    async def status(self) -> dict:
        url = _health_url(self.api_url)
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout, 10.0), transport=self._transport) as http:
                resp = await http.get(url)
        except httpx.HTTPError as exc:
            raise BaalebosConnectionError(
                f"Could not reach the gateway ({url}): {describe_network_error(exc)}"
            ) from exc
        if resp.status_code != 200:
            raise BaalebosUnavailableError(
                f"Health check failed with HTTP {resp.status_code} ({url}).", resp.status_code
            )
        return _json_or_none(resp) or {"status": "ok"}
