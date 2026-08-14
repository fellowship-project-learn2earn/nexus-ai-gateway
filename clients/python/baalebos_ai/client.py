import os
import requests
import httpx

from baalebos_ai.exceptions import (
    BaalebosConfigError,
    BaalebosConnectionError,
    BaalebosAPIError,
    BaalebosAuthError,
)


def _resolve_config(api_url: str, api_key: str):
    api_url = api_url or os.getenv('BAALEBOS_API_URL')
    api_key = api_key or os.getenv('BAALEBOS_API_KEY')

    if not api_url:
        raise BaalebosConfigError(
            'BAALEBOS_API_URL is missing. Set environment variable or pass to constructor.'
        )
    if not api_key:
        raise BaalebosConfigError(
            'BAALEBOS_API_KEY is missing. Set environment variable or pass to constructor.'
        )
    return api_url, api_key


def _build_request(api_key: str, prompt: str, mode: str, temperature: float):
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key,
    }
    payload = {
        'message': prompt,
        'mode': mode,
        'temperature': temperature,
    }
    return headers, payload


def _parse_response(status_code: int, reason: str, data: dict) -> str:
    if status_code == 401:
        raise BaalebosAuthError(
            'Unauthorized - check that BAALEBOS_API_KEY is correct.',
            status_code=401,
        )
    if status_code >= 400:
        raise BaalebosAPIError(
            f'Gateway returned {status_code} {reason}',
            status_code=status_code,
        )

    if 'data' in data and 'choices' in data['data']:
        return data['data']['choices'][0]['message']['content']
    elif 'output' in data:
        return data['output']
    return str(data)


class BaalebosAI:
    """Synchronous client - use this in regular scripts and the CLI."""

    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url, self.api_key = _resolve_config(api_url, api_key)

    def chat(self, prompt: str, mode: str = 'auto', temperature: float = 0.7) -> str:
        headers, payload = _build_request(self.api_key, prompt, mode, temperature)

        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=60)
        except requests.exceptions.Timeout:
            raise BaalebosConnectionError(f'Request to {self.api_url} timed out after 60s.')
        except requests.exceptions.ConnectionError as e:
            raise BaalebosConnectionError(f'Could not reach {self.api_url}: {e}')

        return _parse_response(response.status_code, response.reason, response.json())


class AsyncBaalebosAI:
    """Async client - use this with `await` in async codebases (e.g. FastAPI,
    asyncio scripts). Same behavior and same error types as BaalebosAI, just
    non-blocking. Requires the `httpx` package."""

    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url, self.api_key = _resolve_config(api_url, api_key)

    async def chat(self, prompt: str, mode: str = 'auto', temperature: float = 0.7) -> str:
        headers, payload = _build_request(self.api_key, prompt, mode, temperature)

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise BaalebosConnectionError(f'Request to {self.api_url} timed out after 60s.')
        except httpx.ConnectError as e:
            raise BaalebosConnectionError(f'Could not reach {self.api_url}: {e}')

        return _parse_response(response.status_code, response.reason_phrase, response.json())
