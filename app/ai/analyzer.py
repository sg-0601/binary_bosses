"""
Firmware Analyzer Service
Coordinates prompt generation, Gemini API invocation, and strict Pydantic validation.
"""

import json
from typing import Optional

from app.ai.gemini_client import (
    GeminiClient,
    GeminiError,
    GeminiAPIKeyMissingError,
    GeminiAPIError,
)
from app.ai.prompts import FIRMWARE_ANALYSIS_SYSTEM_PROMPT, build_analysis_prompt
from app.models.firmware import FirmwareAnalysis


class FirmwareAnalysisError(Exception):
    """Base exception for firmware analysis failures."""
    pass


class EmptySourceCodeError(FirmwareAnalysisError):
    """Raised when provided firmware source code is empty or whitespace only."""
    pass


class ModelOutputParsingError(FirmwareAnalysisError):
    """Raised when model output cannot be parsed as valid JSON."""
    pass


class ModelOutputValidationError(FirmwareAnalysisError):
    """Raised when parsed model output fails Pydantic schema validation."""
    pass


class FirmwareAnalyzer:
    """
    Analyzes embedded firmware source code via Gemini and returns validated FirmwareAnalysis.
    """

    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()

    def analyze(
        self,
        source_code: str,
        target_hardware: str = "esp32-devkit-c",
    ) -> FirmwareAnalysis:
        """
        Analyze firmware source code and return a validated FirmwareAnalysis model.

        Raises:
            EmptySourceCodeError: If source_code is empty.
            GeminiAPIKeyMissingError: If Gemini API key is unconfigured.
            GeminiAPIError: If Gemini API call fails.
            ModelOutputParsingError: If model output is not valid JSON.
            ModelOutputValidationError: If model output fails Pydantic validation.
        """
        if not source_code or not source_code.strip():
            raise EmptySourceCodeError("Firmware source code cannot be empty.")

        prompt = build_analysis_prompt(
            source_code=source_code,
            target_hardware=target_hardware,
        )

        raw_text = self.client.generate_content(
            prompt=prompt,
            system_instruction=FIRMWARE_ANALYSIS_SYSTEM_PROMPT,
        )

        cleaned_json = self._extract_json_content(raw_text)

        try:
            parsed_dict = json.loads(cleaned_json)
        except json.JSONDecodeError as exc:
            raise ModelOutputParsingError(f"Model output is not valid JSON: {exc}") from exc

        if not isinstance(parsed_dict, dict):
            raise ModelOutputParsingError("Model output JSON must be an object, not a list or scalar.")

        try:
            analysis = FirmwareAnalysis.model_validate(parsed_dict)
            return analysis
        except Exception as exc:
            raise ModelOutputValidationError(
                f"Model output failed FirmwareAnalysis Pydantic validation: {exc}"
            ) from exc

    @staticmethod
    def _extract_json_content(raw_text: str) -> str:
        """Extract raw JSON string by stripping any markdown code fences."""
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return text


# Global analyzer instance for API usage
analyzer = FirmwareAnalyzer()
