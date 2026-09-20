"""
Unit Tests for Gemini Firmware Analyzer
Verifies Gemini client isolation, prompt generation, strict Pydantic validation,
error handling without silent fallbacks, and golden test structural compatibility.
NO real Gemini API calls are made during tests.
"""

import json
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.ai.gemini_client import (
    GeminiClient,
    GeminiAPIKeyMissingError,
    GeminiAPIError,
)
from app.ai.analyzer import (
    FirmwareAnalyzer,
    EmptySourceCodeError,
    ModelOutputParsingError,
    ModelOutputValidationError,
)
from app.models.firmware import FirmwareAnalysis
from app.utils.config import settings


@pytest.fixture
def fan_controller_source() -> str:
    """Read fan controller C source code."""
    path = settings.PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "main.c"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def fan_controller_golden_json_str() -> str:
    """Read fan controller golden analysis JSON string."""
    path = settings.PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "firmware_analysis.json"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def mock_gemini_client(fan_controller_golden_json_str: str) -> MagicMock:
    """Create a mock Gemini client returning valid JSON."""
    client = MagicMock(spec=GeminiClient)
    client.is_configured = True
    client.generate_content.return_value = fan_controller_golden_json_str
    return client


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_valid_response_to_firmware_analysis(fan_controller_source: str, mock_gemini_client: MagicMock):
    """Verify a valid model response parses into a structured FirmwareAnalysis model."""
    analyzer = FirmwareAnalyzer(client=mock_gemini_client)
    result = analyzer.analyze(source_code=fan_controller_source, target_hardware="esp32-devkit-c")

    assert isinstance(result, FirmwareAnalysis)
    assert result.firmware_name == "fan_controller"
    assert result.target_hardware.board == "esp32-devkit-c"
    assert result.language == "C"
    assert len(result.inputs) >= 1
    assert len(result.outputs) >= 2
    assert len(result.states) == 4
    mock_gemini_client.generate_content.assert_called_once()


def test_malformed_response_raises_parsing_error(mock_gemini_client: MagicMock):
    """Verify non-JSON model response raises ModelOutputParsingError."""
    mock_gemini_client.generate_content.return_value = "This is not JSON: { broken syntax ... "
    analyzer = FirmwareAnalyzer(client=mock_gemini_client)

    with pytest.raises(ModelOutputParsingError) as exc_info:
        analyzer.analyze(source_code="int main() {}", target_hardware="esp32")

    assert "not valid json" in str(exc_info.value).lower()


def test_missing_required_data_raises_validation_error(mock_gemini_client: MagicMock):
    """Verify valid JSON missing required FirmwareAnalysis fields raises ModelOutputValidationError."""
    # Missing required target_hardware and language
    incomplete_json = json.dumps({"firmware_name": "broken_fw"})
    mock_gemini_client.generate_content.return_value = incomplete_json
    analyzer = FirmwareAnalyzer(client=mock_gemini_client)

    with pytest.raises(ModelOutputValidationError) as exc_info:
        analyzer.analyze(source_code="void setup() {}", target_hardware="arduino-uno")

    assert "validation" in str(exc_info.value).lower()


def test_empty_source_code_raises_error():
    """Verify empty or whitespace-only source code raises EmptySourceCodeError without calling API."""
    mock_client = MagicMock(spec=GeminiClient)
    analyzer = FirmwareAnalyzer(client=mock_client)

    with pytest.raises(EmptySourceCodeError):
        analyzer.analyze(source_code="")

    with pytest.raises(EmptySourceCodeError):
        analyzer.analyze(source_code="   \n\t   ")

    mock_client.generate_content.assert_not_called()


def test_api_failure_propagates():
    """Verify Gemini API failure raises GeminiAPIError."""
    mock_client = MagicMock(spec=GeminiClient)
    mock_client.generate_content.side_effect = GeminiAPIError("HTTP 503: Service Unavailable")
    analyzer = FirmwareAnalyzer(client=mock_client)

    with pytest.raises(GeminiAPIError) as exc_info:
        analyzer.analyze(source_code="int main() { return 0; }")

    assert "503" in str(exc_info.value)


def test_missing_api_key_raises_error():
    """Verify unconfigured client raises GeminiAPIKeyMissingError."""
    client = GeminiClient(api_key="")
    analyzer = FirmwareAnalyzer(client=client)

    with pytest.raises(GeminiAPIKeyMissingError):
        analyzer.analyze(source_code="int main() {}")


def test_target_hardware_passed_correctly(fan_controller_source: str, mock_gemini_client: MagicMock):
    """Verify target hardware parameter is embedded into the prompt sent to Gemini."""
    analyzer = FirmwareAnalyzer(client=mock_gemini_client)
    analyzer.analyze(source_code=fan_controller_source, target_hardware="rp2040-raspberry-pi-pico")

    prompt_sent = mock_gemini_client.generate_content.call_args.kwargs["prompt"]
    assert "rp2040-raspberry-pi-pico" in prompt_sent


def test_no_hallucinated_fallback_data(mock_gemini_client: MagicMock):
    """Verify analyzer never catches exceptions and returns fake fallback data."""
    mock_gemini_client.generate_content.side_effect = RuntimeError("Fatal network outage")
    analyzer = FirmwareAnalyzer(client=mock_gemini_client)

    # It must raise, NOT return a dummy FirmwareAnalysis object
    with pytest.raises(RuntimeError):
        analyzer.analyze(source_code="void loop() {}")


def test_golden_test_fan_controller_compatibility(
    fan_controller_source: str,
    fan_controller_golden_json_str: str,
    mock_gemini_client: MagicMock,
):
    """
    GOLDEN TEST:
    Compare mocked Gemini response against existing fan_controller analysis.
    Verifies structural and behavioral compatibility without requiring strict byte equality.
    """
    analyzer = FirmwareAnalyzer(client=mock_gemini_client)
    analyzed = analyzer.analyze(source_code=fan_controller_source, target_hardware="esp32-devkit-c")

    golden = FirmwareAnalysis.model_validate_json(fan_controller_golden_json_str)

    # 1. High-level metadata compatibility
    assert analyzed.firmware_name == golden.firmware_name
    assert analyzed.language == golden.language
    assert analyzed.target_hardware.board == golden.target_hardware.board

    # 2. Hardware components compatibility
    analyzed_output_names = {o.name for o in analyzed.outputs}
    golden_output_names = {o.name for o in golden.outputs}
    assert "FAN_PIN" in analyzed_output_names
    assert golden_output_names.issubset(analyzed_output_names)

    # 3. State machine structure compatibility
    analyzed_states = {s.name for s in analyzed.states}
    golden_states = {s.name for s in golden.states}
    assert golden_states == analyzed_states

    # 4. Boundary condition discovery compatibility
    golden_threshold = next(bc.threshold for bc in golden.boundary_conditions if bc.threshold is not None)
    analyzed_threshold = next(bc.threshold for bc in analyzed.boundary_conditions if bc.threshold is not None)
    assert analyzed_threshold == golden_threshold == 30.0

    # 5. Sensor limits compatibility
    golden_min_limit = next(bc.min_limit for bc in golden.boundary_conditions if bc.min_limit is not None)
    golden_max_limit = next(bc.max_limit for bc in golden.boundary_conditions if bc.max_limit is not None)
    assert golden_min_limit == -20.0
    assert golden_max_limit == 120.0


def test_api_endpoint_analyze_success(fan_controller_golden_json_str: str, monkeypatch):
    """Verify POST /api/firmware/analyze returns 200 and valid FirmwareAnalysis."""
    client = TestClient(app)

    # Mock the global analyzer instance
    mock_analyzer = MagicMock()
    mock_analyzer.analyze.return_value = FirmwareAnalysis.model_validate_json(fan_controller_golden_json_str)
    monkeypatch.setattr("app.main.analyzer", mock_analyzer)

    payload = {
        "source_code": "int main() { return 0; }",
        "target_hardware": "esp32-devkit-c"
    }

    response = client.post("/api/firmware/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["firmware_name"] == "fan_controller"
    assert data["target_hardware"]["board"] == "esp32-devkit-c"
    assert len(data["states"]) == 4


def test_api_endpoint_analyze_error_handling(monkeypatch):
    """Verify POST /api/firmware/analyze error code mapping."""
    client = TestClient(app)

    # 1. Empty source code -> 400
    mock_analyzer = MagicMock()
    mock_analyzer.analyze.side_effect = EmptySourceCodeError("Firmware source code cannot be empty.")
    monkeypatch.setattr("app.main.analyzer", mock_analyzer)

    resp_400 = client.post("/api/firmware/analyze", json={"source_code": ""})
    assert resp_400.status_code == 400

    # 2. Missing API key -> 503
    mock_analyzer.analyze.side_effect = GeminiAPIKeyMissingError("Gemini API key is not configured.")
    resp_503 = client.post("/api/firmware/analyze", json={"source_code": "int main() {}"})
    assert resp_503.status_code == 503

    # 3. Model output parsing failure -> 502
    mock_analyzer.analyze.side_effect = ModelOutputParsingError("Malformed model output")
    resp_502 = client.post("/api/firmware/analyze", json={"source_code": "int main() {}"})
    assert resp_502.status_code == 502


def test_security_api_key_not_leaked():
    """Security check: verify API key is never exposed in error representations."""
    secret_key = "AIzaSySecretFakeApiKey123456789"
    client = GeminiClient(api_key=secret_key)

    # String representation should not contain the secret
    assert secret_key not in str(client)
    assert secret_key not in repr(client)

    # Missing key error should not contain any secret
    missing_err = GeminiAPIKeyMissingError("Gemini API key is not configured.")
    assert secret_key not in str(missing_err)
