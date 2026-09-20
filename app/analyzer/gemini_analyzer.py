import json
import os
import httpx
from typing import Optional
from app.models.schemas import FirmwareAnalysis, FailureAnalysis, TestCase
from app.utils.config import settings


class GeminiFirmwareAnalyzer:
    """Uses Google Gemini API to analyze C/C++ firmware and diagnose simulation failures."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        self.model = settings.GEMINI_MODEL or "gemini-3.1-flash-lite"
        self.timeout = settings.GEMINI_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        return bool(self.api_key.strip())

    def analyze_firmware(self, c_code: str) -> FirmwareAnalysis:
        """Analyze embedded C firmware code to extract peripherals, states, thresholds, and risks."""
        if not self.is_configured():
            return FirmwareAnalysis(
                project_name="fan_controller",
                summary="Gemini API key not configured. Static fallback analysis applied.",
                peripherals=["Serial (115200)", "GPIO13 (Fan Relay)", "DHT22 (Sensor)"],
                thresholds={"TEMP_THRESHOLD": 30.0},
                expected_states=["FIRMWARE_TEST_STARTED", "FAN_ON", "FIRMWARE_TEST_SUCCESS"],
                potential_risks=["No hardware sensor timeout", "Missing hysteresis"]
            )

        prompt = (
            "You are an expert embedded firmware QA engineer. "
            "Analyze the following C/C++ firmware code and output ONLY valid JSON matching this schema:\n"
            "{\n"
            '  "project_name": "string",\n'
            '  "summary": "string",\n'
            '  "peripherals": ["string"],\n'
            '  "thresholds": {"key": float},\n'
            '  "expected_states": ["string"],\n'
            '  "potential_risks": ["string"]\n'
            "}\n\n"
            f"FIRMWARE SOURCE CODE:\n```c\n{c_code}\n```"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1
            }
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidate = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(candidate)
                    return FirmwareAnalysis(
                        project_name=parsed.get("project_name", "firmware_project"),
                        summary=parsed.get("summary", "Automated analysis"),
                        peripherals=parsed.get("peripherals", []),
                        thresholds=parsed.get("thresholds", {}),
                        expected_states=parsed.get("expected_states", []),
                        potential_risks=parsed.get("potential_risks", [])
                    )
                else:
                    return FirmwareAnalysis(
                        project_name="fan_controller",
                        summary=f"Gemini API returned HTTP {res.status_code}: {res.text[:150]}",
                        peripherals=["Serial", "GPIO13", "DHT22"],
                        thresholds={"TEMP_THRESHOLD": 30.0},
                        expected_states=["FIRMWARE_TEST_STARTED", "FAN_ON", "FIRMWARE_TEST_SUCCESS"],
                        potential_risks=["API response unparsable"]
                    )
        except Exception as e:
            return FirmwareAnalysis(
                project_name="fan_controller",
                summary=f"Gemini analysis error ({e})",
                peripherals=["Serial", "GPIO13", "DHT22"],
                thresholds={"TEMP_THRESHOLD": 30.0},
                expected_states=["FIRMWARE_TEST_STARTED", "FAN_ON", "FIRMWARE_TEST_SUCCESS"],
                potential_risks=[str(e)]
            )

    def analyze_failure(self, c_code: str, test_case: TestCase, captured_serial: str, error_msg: str) -> FailureAnalysis:
        """Diagnose why simulation failed and suggest firmware patch."""
        if not self.is_configured():
            return FailureAnalysis(
                status="DIAGNOSED",
                bug_detected=True,
                root_cause=f"Test '{test_case.name}' failed. Expected '{test_case.expected_serial}' not found.",
                affected_lines="setup() / loop()",
                suggested_fix="Verify serial baud rate and pin state logic."
            )

        prompt = (
            "You are an embedded firmware debugging expert. "
            "A firmware test failed inside the Wokwi simulator. "
            "Diagnose the root cause and output ONLY valid JSON matching this schema:\n"
            "{\n"
            '  "status": "string",\n'
            '  "bug_detected": boolean,\n'
            '  "root_cause": "string",\n'
            '  "affected_lines": "string",\n'
            '  "suggested_fix": "string"\n'
            "}\n\n"
            f"FIRMWARE CODE:\n```c\n{c_code}\n```\n\n"
            f"TEST CASE:\nName: {test_case.name}\nExpected Serial: {test_case.expected_serial}\n\n"
            f"ACTUAL CAPTURED SERIAL LOGS:\n```\n{captured_serial}\n```\n\n"
            f"ERROR MESSAGE:\n{error_msg}"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1}
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    parsed = json.loads(res.json()["candidates"][0]["content"]["parts"][0]["text"])
                    return FailureAnalysis(
                        status=parsed.get("status", "ANALYZED"),
                        bug_detected=parsed.get("bug_detected", True),
                        root_cause=parsed.get("root_cause", "Observed serial divergence from expected invariant."),
                        affected_lines=parsed.get("affected_lines"),
                        suggested_fix=parsed.get("suggested_fix")
                    )
        except Exception as e:
            pass

        return FailureAnalysis(
            status="ERROR",
            bug_detected=True,
            root_cause=f"Diagnostic error: {error_msg}",
            affected_lines="Unknown",
            suggested_fix="Inspect serial output and Wokwi pin connections."
        )


analyzer = GeminiFirmwareAnalyzer()
