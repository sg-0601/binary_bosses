"""
Unit Tests for Deterministic Evaluator and Scenario Generator
Verifies that:
- Mock execution can NEVER produce PASS (always produces MOCK)
- Missing resources produce ERROR
- Real Wokwi exit code 0 and matching serial pattern produce PASS
- Non-matching serial pattern produces FAIL
- Scenario generator creates valid isolated project directories
"""

import pytest
from pathlib import Path

from app.models.test_case import TestCase, TestCategory, TestPriority
from app.models.schemas import SimulationResult
from app.tests.evaluator import TestEvaluator, evaluator
from app.simulator.scenario_generator import ScenarioGenerator, scenario_generator
from app.services.artifact_provider import ExecutionArtifactProvider, artifact_provider


def test_mock_execution_never_produces_pass():
    """Verify that mock simulation ALWAYS evaluates to MOCK, never PASS."""
    tc = TestCase(
        id="TC_MOCK_TEST",
        name="Mock Test Case",
        category=TestCategory.NORMAL,
        description="Verifies mock fallback evaluation rule",
        priority=TestPriority.MEDIUM,
        preconditions=["None"],
        inputs={},
        actions=["Run mock simulation"],
        expected_outputs={},
        expected_behavior="Should not pass",
        failure_conditions=["Mock passes"],
        hardware_requirements={"board": "esp32-devkit-c"},
        expected_serial_log="Some String"
    )

    # Simulation marked with mock_used=True, even if exit_code=0 and captured serial matches
    sim_res = SimulationResult(
        success=False,
        exit_code=0,
        captured_serial="Some String in captured serial",
        matched_expected=True,
        stdout="Mock simulation output",
        is_real_execution=False,
        mock_used=True
    )

    result = evaluator.evaluate(tc, sim_res)
    assert result.status == "MOCK", f"Expected status 'MOCK', got '{result.status}'"
    assert result.status != "PASS", "CRITICAL RULE VIOLATION: Mock execution must NEVER produce PASS"


def test_non_real_execution_produces_error():
    """Verify that non-real execution produces ERROR status."""
    tc = TestCase(
        id="TC_ERR_TEST",
        name="Error Test Case",
        category=TestCategory.NORMAL,
        description="Verifies non-real execution handling",
        priority=TestPriority.MEDIUM,
        preconditions=["None"],
        inputs={},
        actions=["Simulate failure"],
        expected_outputs={},
        expected_behavior="Error handling",
        failure_conditions=["Fails to error"],
        hardware_requirements={"board": "esp32-devkit-c"},
    )

    sim_res = SimulationResult(
        success=False,
        exit_code=1,
        captured_serial="",
        stderr="AUTHENTICATION ERROR: WOKWI_CLI_TOKEN is not configured",
        is_real_execution=False,
        mock_used=False
    )

    result = evaluator.evaluate(tc, sim_res)
    assert result.status == "ERROR"


def test_real_matching_execution_produces_pass():
    """Verify that real execution with exit code 0 and matching serial pattern produces PASS."""
    tc = TestCase(
        id="TC_PASS_TEST",
        name="Passing Test Case",
        category=TestCategory.NORMAL,
        description="Verifies PASS evaluation",
        priority=TestPriority.HIGH,
        preconditions=["System booted"],
        inputs={},
        actions=["Check boot"],
        expected_outputs={},
        expected_behavior="Boot announcement",
        failure_conditions=["Boot missing"],
        hardware_requirements={"board": "esp32-devkit-c"},
        expected_serial_log="[SYSTEM_BOOT] Industrial Firmware v1.0.0"
    )

    sim_res = SimulationResult(
        success=True,
        exit_code=0,
        captured_serial="[SYSTEM_BOOT] Industrial Firmware v1.0.0 initializing...\nReady.",
        matched_expected=True,
        is_real_execution=True,
        mock_used=False
    )

    result = evaluator.evaluate(tc, sim_res)
    assert result.status == "PASS"
    assert "Serial pattern" in result.matched_conditions[1]


def test_real_mismatched_execution_produces_fail():
    """Verify that missing expected serial pattern produces FAIL."""
    tc = TestCase(
        id="TC_FAIL_TEST",
        name="Failing Test Case",
        category=TestCategory.BOUNDARY,
        description="Verifies FAIL evaluation",
        priority=TestPriority.HIGH,
        preconditions=["System booted"],
        inputs={},
        actions=["Check threshold"],
        expected_outputs={},
        expected_behavior="Exceeded output",
        failure_conditions=["Threshold missing"],
        hardware_requirements={"board": "esp32-devkit-c"},
        expected_serial_log="Threshold Exceeded"
    )

    sim_res = SimulationResult(
        success=False,
        exit_code=42,  # Wokwi timeout
        captured_serial="[SYSTEM_BOOT] Normal Range (<=30.0 C). Fan: OFF",
        matched_expected=False,
        is_real_execution=True,
        mock_used=False
    )

    result = evaluator.evaluate(tc, sim_res)
    assert result.status == "FAIL"
    assert any("NOT found" in f for f in result.failed_conditions)


def test_scenario_generator_creates_isolated_project(tmp_path):
    """Verify scenario generator builds a complete, isolated Wokwi directory."""
    tc = TestCase(
        id="TC_ISO_01",
        name="Isolated Project Test",
        category=TestCategory.NORMAL,
        description="Verifies directory creation",
        priority=TestPriority.MEDIUM,
        preconditions=["None"],
        inputs={},
        actions=["Generate"],
        expected_outputs={},
        expected_behavior="Boot",
        failure_conditions=["None"],
        hardware_requirements={"board": "esp32-devkit-c"},
        expected_serial_log="[SYSTEM_BOOT]"
    )

    gen_scenario = scenario_generator.generate(tc, run_dir=tmp_path)

    project_dir = Path(gen_scenario.project_dir)
    assert project_dir.exists()
    assert (project_dir / "scenario.yaml").exists()
    assert (project_dir / "wokwi.toml").exists()
    assert (project_dir / "diagram.json").exists()
    assert (project_dir / "fan_controller.ino.bin").exists()


def test_artifact_provider_demo_mode():
    """Verify artifact provider validates the presence of DEMO mode files."""
    assert artifact_provider.mode == "demo"
    assert artifact_provider.validate() is True
    info = artifact_provider.get_artifact_info()
    assert "DEMO MODE" in info["notice"]
