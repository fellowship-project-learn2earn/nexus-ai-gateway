import os
import requests

from .auth import get_api_key

DEFAULT_API_URL = "https://gateway.baalebo.xyz/webhook/baalebos-ai"


class BaalebosAI:
    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url = api_url or os.getenv("BAALEBOS_API_URL", DEFAULT_API_URL)
        self.api_key = api_key or get_api_key()

    def chat(self, prompt: str, mode: str = "auto") -> str:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }
        payload = {"message": prompt, "mode": mode}

        response = requests.post(self.api_url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()

        if "output" in data:
            return data["output"]
        if "text" in data:
            return data["text"]
        return str(data)
