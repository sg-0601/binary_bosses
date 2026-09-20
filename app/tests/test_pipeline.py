import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.compiler.gcc_compiler import compiler
from app.simulator.wokwi_runner import simulator
from app.models.schemas import SimulationRequest
from app.ai.analyzer import analyzer
from app.tests.generator import DeterministicTestGenerator
from app.utils.config import settings

client = TestClient(app)


def test_health_endpoint():
    """Verify health endpoint detects installed tools and environment mode."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["wokwi_cli_installed"] is True
    assert data["firmware_execution_mode"] == "demo"
    assert "0.27" in simulator.get_version()


def test_dashboard_endpoint():
    """Verify HTML dashboard renders cleanly."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Embedded Firmware Testing System" in response.text


def test_gemini_firmware_analysis():
    """Verify Gemini AI parses C firmware into structured Pydantic analysis."""
    src_file = settings.PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "main.c"
    c_code = src_file.read_text(encoding="utf-8")
    
    analysis = analyzer.analyze(source_code=c_code, target_hardware="esp32-devkit-c")
    assert analysis is not None
    assert analysis.firmware_name is not None
    assert len(analysis.peripherals) > 0


def test_deterministic_test_generator():
    """Verify DeterministicTestGenerator derives categorized TestSuite."""
    src_file = settings.PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "main.c"
    c_code = src_file.read_text(encoding="utf-8")
    analysis = analyzer.analyze(source_code=c_code, target_hardware="esp32-devkit-c")
    
    generator = DeterministicTestGenerator(analysis)
    suite = generator.generate()
    assert suite.total_tests > 0
    assert len(suite.test_cases) > 0
    assert suite.target_hardware == "esp32-devkit-c"


def test_real_wokwi_simulation():
    """
    Verify real Wokwi CLI execution.
    Fails or skips if WOKWI_CLI_TOKEN is absent; strictly requires real execution.
    """
    if not simulator.has_token():
        pytest.skip("WOKWI_CLI_TOKEN is not configured in environment. Skipping real Wokwi run.")

    project_dir = settings.PROJECT_ROOT / "wokwi" / "projects" / "fan_controller"
    req = SimulationRequest(
        project_dir=str(project_dir),
        timeout_ms=8000,
        expect_text="[SYSTEM_BOOT]",
        scenario_file="scenario.yaml",
        use_mock_fallback=False  # Strictly real execution
    )
    res = simulator.run_simulation(req)

    assert res.is_real_execution is True, "Must be real Wokwi execution"
    assert res.mock_used is False, "Mock simulation must NOT be used"
    assert res.exit_code == 0, f"Wokwi CLI exited with code {res.exit_code}: {res.stderr}"
    assert res.success is True
    assert "[SYSTEM_BOOT]" in res.captured_serial


def test_full_pipeline_api():
    """
    Verify end-to-end endpoint /api/run-test:
    uploaded C firmware -> Gemini analysis -> Test generation -> Wokwi CLI -> Serial capture.
    """
    if not simulator.has_token():
        pytest.skip("WOKWI_CLI_TOKEN is not configured in environment. Skipping real API test.")

    payload = {
        "test_name": "ESP32 Real Execution Pipeline Test",
        "project_dir": "wokwi/projects/fan_controller",
        "source_file": "firmware/examples/fan_controller/main.c",
        "expect_text": "[SYSTEM_BOOT]",
        "timeout_ms": 8000,
        "use_mock_fallback": False
    }
    response = client.post("/api/run-test", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PASSED"
    assert data["is_real_execution"] is True, "Pipeline must confirm real execution"
    assert data["mock_used"] is False, "Pipeline must confirm mock was not used"
    assert "[SYSTEM_BOOT]" in data["serial_output"]
    assert "test_id" in data
    assert "firmware_analysis" in data["details"]
    assert "test_suite_generated" in data["details"]
