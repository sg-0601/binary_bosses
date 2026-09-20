"""
AI Module for Autonomous Embedded Firmware Testing
"""

from app.ai.gemini_client import (
    GeminiClient,
    GeminiError,
    GeminiAPIKeyMissingError,
    GeminiAPIError,
)
from app.ai.prompts import (
    FIRMWARE_ANALYSIS_SYSTEM_PROMPT,
    build_analysis_prompt,
)
from app.ai.analyzer import (
    FirmwareAnalyzer,
    FirmwareAnalysisError,
    EmptySourceCodeError,
    ModelOutputParsingError,
    ModelOutputValidationError,
    analyzer,
)

__all__ = [
    "GeminiClient",
    "GeminiError",
    "GeminiAPIKeyMissingError",
    "GeminiAPIError",
    "FIRMWARE_ANALYSIS_SYSTEM_PROMPT",
    "build_analysis_prompt",
    "FirmwareAnalyzer",
    "FirmwareAnalysisError",
    "EmptySourceCodeError",
    "ModelOutputParsingError",
    "ModelOutputValidationError",
    "analyzer",
]
