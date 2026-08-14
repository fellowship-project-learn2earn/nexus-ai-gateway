import os
import requests

from baalebos_ai.exceptions import (
    BaalebosConfigError,
    BaalebosConnectionError,
    BaalebosAPIError,
    BaalebosAuthError,
)


class BaalebosAI:
    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url = api_url or os.getenv('BAALEBOS_API_URL')
        self.api_key = api_key or os.getenv('BAALEBOS_API_KEY')

        if not self.api_url:
            raise BaalebosConfigError(
                'BAALEBOS_API_URL is missing. Set environment variable or pass to constructor.'
            )
        if not self.api_key:
            raise BaalebosConfigError(
                'BAALEBOS_API_KEY is missing. Set environment variable or pass to constructor.'
            )

    def chat(self, prompt: str, mode: str = 'auto', temperature: float = 0.7) -> str:
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.api_key
        }
        payload = {
            'message': prompt,
            'mode': mode,
            'temperature': temperature
        }

        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=60)
        except requests.exceptions.Timeout:
            raise BaalebosConnectionError(f'Request to {self.api_url} timed out after 60s.')
        except requests.exceptions.ConnectionError as e:
            raise BaalebosConnectionError(f'Could not reach {self.api_url}: {e}')

        if response.status_code == 401:
            raise BaalebosAuthError(
                'Unauthorized - check that BAALEBOS_API_KEY is correct.',
                status_code=401,
            )
        if not response.ok:
            raise BaalebosAPIError(
                f'Gateway returned {response.status_code} {response.reason}',
                status_code=response.status_code,
            )

        data = response.json()

        if 'data' in data and 'choices' in data['data']:
            return data['data']['choices'][0]['message']['content']
        elif 'output' in data:
            return data['output']
        return str(data)