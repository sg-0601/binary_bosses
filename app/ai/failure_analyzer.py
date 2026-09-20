"""
AI Failure Analyzer
Uses Gemini to explain WHY a test failed, AFTER deterministic PASS/FAIL.

This is NOT the PASS/FAIL authority. It provides diagnostic explanation only.
"""

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.ai.gemini_client import GeminiClient, GeminiError


class FailureAnalysisResult(BaseModel):
    """AI-generated explanation of a test failure."""
    summary: str = Field("", description="Brief summary of the failure")
    probable_causes: List[str] = Field(default_factory=list, description="Probable root causes")
    relevant_firmware_sections: List[str] = Field(default_factory=list,
        description="Relevant code sections or functions")
    evidence: List[str] = Field(default_factory=list, description="Evidence supporting the analysis")
    suggested_fix: str = Field("", description="Suggested remediation")
    confidence: float = Field(0.0, description="Confidence score 0.0-1.0")
    ai_disclaimer: str = Field(
        default="AI Failure Analysis — This is an AI-generated explanation, not the PASS/FAIL authority.",
        description="Disclaimer label")


class FailureAnalyzer:
    """
    Sends test failure context to Gemini for diagnostic explanation.
    
    Labeled clearly as "AI Failure Analysis" — it is an explanation, not the authority.
    If Gemini is unavailable, the test result remains valid without analysis.
    """

    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()

    def analyze_failure(
        self,
        test_id: str,
        test_name: str,
        expected_behavior: str,
        observed_serial: str,
        firmware_source: str = "",
        firmware_analysis_summary: str = "",
        wokwi_errors: str = "",
    ) -> FailureAnalysisResult:
        """
        Generate AI failure analysis for a failed test.
        
        Returns FailureAnalysisResult even on Gemini failure (with empty fields).
        """
        if not self.client.is_configured:
            return FailureAnalysisResult(
                summary="Gemini API key not configured — failure analysis unavailable.",
                confidence=0.0,
            )

        prompt = self._build_prompt(
            test_id=test_id,
            test_name=test_name,
            expected_behavior=expected_behavior,
            observed_serial=observed_serial,
            firmware_source=firmware_source,
            firmware_analysis_summary=firmware_analysis_summary,
            wokwi_errors=wokwi_errors,
        )

        try:
            raw = self.client.generate_content(prompt=prompt)
            return self._parse_response(raw)
        except GeminiError:
            return FailureAnalysisResult(
                summary="Gemini API error — failure analysis unavailable.",
                confidence=0.0,
            )
        except Exception:
            return FailureAnalysisResult(
                summary="Unexpected error during failure analysis.",
                confidence=0.0,
            )

    def _build_prompt(self, **kwargs) -> str:
        return f"""You are an embedded firmware test failure analyst.

A firmware test has FAILED. Analyze the failure and provide a structured diagnosis.

Test ID: {kwargs.get('test_id', 'unknown')}
Test Name: {kwargs.get('test_name', 'unknown')}

EXPECTED BEHAVIOR:
{kwargs.get('expected_behavior', 'N/A')}

OBSERVED SERIAL OUTPUT:
{kwargs.get('observed_serial', 'N/A')[:2000]}

WOKWI EXECUTION ERRORS:
{kwargs.get('wokwi_errors', 'None')}

FIRMWARE SOURCE (excerpt):
{kwargs.get('firmware_source', 'N/A')[:3000]}

FIRMWARE ANALYSIS SUMMARY:
{kwargs.get('firmware_analysis_summary', 'N/A')[:1000]}

Respond with a JSON object:
{{
  "summary": "one-line failure summary",
  "probable_causes": ["cause1", "cause2"],
  "relevant_firmware_sections": ["function or section names"],
  "evidence": ["evidence point 1", "evidence point 2"],
  "suggested_fix": "recommended fix",
  "confidence": 0.8
}}
"""

    def _parse_response(self, raw: str) -> FailureAnalysisResult:
        """Parse Gemini response into FailureAnalysisResult."""
        try:
            text = raw.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                lines = lines[1:] if lines[0].startswith("```") else lines
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

            data = json.loads(text)
            return FailureAnalysisResult(
                summary=data.get("summary", ""),
                probable_causes=data.get("probable_causes", []),
                relevant_firmware_sections=data.get("relevant_firmware_sections", []),
                evidence=data.get("evidence", []),
                suggested_fix=data.get("suggested_fix", ""),
                confidence=float(data.get("confidence", 0.5)),
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return FailureAnalysisResult(
                summary=raw[:500] if raw else "Could not parse failure analysis.",
                confidence=0.3,
            )


failure_analyzer = FailureAnalyzer()
