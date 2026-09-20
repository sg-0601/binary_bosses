"""
Gemini API Client
Isolated lightweight client for the Google Gemini Generative Language REST API.
"""

import os
import time
from typing import Optional
import httpx

from app.utils.config import settings


class GeminiError(Exception):
    """Base exception for Gemini client errors."""
    pass


class GeminiAPIKeyMissingError(GeminiError):
    """Raised when Gemini API key is missing from environment configuration."""
    pass


class GeminiAPIError(GeminiError):
    """Raised when Gemini API returns an error or fails to respond."""
    pass


class GeminiClient:
    """
    Lightweight client for communicating with the Gemini REST API.
    Isolated from the rest of the application.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        if api_key is not None:
            self._api_key = api_key
        else:
            self._api_key = os.environ.get("GEMINI_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", "")

        if model is not None:
            self.model = model
        else:
            self.model = os.environ.get("GEMINI_MODEL", "") or getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Check if client has a valid API key configured."""
        return bool(self._api_key and self._api_key.strip())

    def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        """
        Send a content generation request to the Gemini API and return raw JSON response text.

        Never logs or leaks the API key in exception messages.
        """
        if not self.is_configured:
            raise GeminiAPIKeyMissingError(
                "Gemini API key is not configured. Please set the GEMINI_API_KEY environment variable."
            )

        endpoint = f"{self.BASE_URL}/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}],
            }

        response = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(endpoint, headers=headers, json=payload)
                if response.status_code == 200:
                    break
                if response.status_code in (429, 503) and attempt < max_retries - 1:
                    if response.status_code == 429:
                        import re
                        m = re.search(r"Please retry in ([0-9.]+)s", response.text)
                        sleep_time = float(m.group(1)) + 2.0 if m else 30.0
                    else:
                        sleep_time = 5 * (attempt + 1)
                    time.sleep(sleep_time)
                    continue
                raise GeminiAPIError(
                    f"Gemini API returned HTTP {response.status_code}: {response.text[:500]}"
                )
            except httpx.RequestError as exc:
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise GeminiAPIError(f"Network error communicating with Gemini API: {type(exc).__name__}") from exc

        try:
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise GeminiAPIError("Gemini API response contained no candidates.")
            
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts or "text" not in parts[0]:
                raise GeminiAPIError("Gemini API candidate contained no text content.")

            return parts[0]["text"]
        except Exception as exc:
            if isinstance(exc, GeminiAPIError):
                raise
            raise GeminiAPIError(f"Failed to parse Gemini API response: {exc}") from exc
