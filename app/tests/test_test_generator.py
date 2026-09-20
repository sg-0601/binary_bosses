"""
Unit Tests for Deterministic Firmware Test Generator
Verifies test generation rules, boundary discovery, failure handling, and schema integrity.
"""

import pytest
from pathlib import Path

from app.models.firmware import (
    FirmwareAnalysis,
    TargetHardware,
    CommunicationInterface,
    ErrorHandlingRule,
    BoundaryCondition,
    FirmwareState,
    StateTransition,
    Sensor,
    Actuator,
)
from app.models.test_case import TestCase, TestSuite, TestCategory, TestPriority
from app.tests.generator import generate_tests, DeterministicTestGenerator
from app.utils.config import settings


@pytest.fixture
def fan_controller_analysis() -> FirmwareAnalysis:
    """Load fan controller firmware analysis fixture."""
    json_path = settings.PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "firmware_analysis.json"
    assert json_path.exists(), f"Missing fan controller analysis at {json_path}"
    return FirmwareAnalysis.from_json_file(json_path)


@pytest.fixture
def fan_controller_suite(fan_controller_analysis: FirmwareAnalysis) -> TestSuite:
    """Generate test suite for fan controller once for fixture use."""
    return generate_tests(fan_controller_analysis)


def test_1_fan_controller_generates_normal_tests(fan_controller_suite: TestSuite):
    """1. Verify Fan Controller generates normal tests (boot and steady-state operating)."""
    normal_tests = fan_controller_suite.filter_by_category(TestCategory.NORMAL)
    assert len(normal_tests) >= 2, f"Expected at least 2 NORMAL tests, got {len(normal_tests)}"

    # Check for boot test
    boot_test = next((tc for tc in normal_tests if "boot" in tc.name.lower() or "init" in tc.name.lower()), None)
    assert boot_test is not None, "Missing system boot/initialization normal test"
    assert boot_test.priority == TestPriority.CRITICAL
    assert "power" in boot_test.inputs

    # Check for normal temperature monitoring test
    temp_normal = next((tc for tc in normal_tests if "nominal" in tc.name.lower() or "25.0" in tc.name), None)
    assert temp_normal is not None, "Missing nominal normal operating temperature test"
    assert temp_normal.expected_outputs.get("FAN_PIN") == "LOW"


def test_2_threshold_boundary_tests_are_generated(fan_controller_suite: TestSuite):
    """2. Verify threshold boundary tests are generated around 30°C: below (29°C), exact (30°C), above (31°C)."""
    boundary_tests = fan_controller_suite.filter_by_category(TestCategory.BOUNDARY)
    threshold_tests = [tc for tc in boundary_tests if tc.metadata.get("boundary_type") == "threshold"]

    assert len(threshold_tests) == 3, f"Expected exactly 3 threshold tests (29, 30, 31), got {len(threshold_tests)}"

    positions = {tc.metadata.get("position"): tc.inputs.get("temperature") for tc in threshold_tests}
    assert "below" in positions and positions["below"] == 29.0, f"Missing 29.0 C below threshold test, got {positions}"
    assert "exact" in positions and positions["exact"] == 30.0, f"Missing 30.0 C exact threshold test, got {positions}"
    assert "above" in positions and positions["above"] == 31.0, f"Missing 31.0 C above threshold test, got {positions}"

    # Verify expected outputs: 29 and 30 keep fan OFF, 31 turns fan ON
    below_tc = next(tc for tc in threshold_tests if tc.metadata.get("position") == "below")
    assert below_tc.expected_outputs.get("FAN_PIN") == "LOW"

    exact_tc = next(tc for tc in threshold_tests if tc.metadata.get("position") == "exact")
    assert exact_tc.expected_outputs.get("FAN_PIN") == "LOW"

    above_tc = next(tc for tc in threshold_tests if tc.metadata.get("position") == "above")
    assert above_tc.expected_outputs.get("FAN_PIN") == "HIGH"


def test_3_sensor_boundary_tests_are_generated(fan_controller_suite: TestSuite):
    """3. Verify documented sensor limit boundary tests are generated (-20°C, 120°C, below -20°C, above 120°C)."""
    boundary_tests = fan_controller_suite.filter_by_category(TestCategory.BOUNDARY)
    sensor_limits = [tc for tc in boundary_tests if tc.metadata.get("boundary_type") == "sensor_limit"]

    assert len(sensor_limits) >= 4, f"Expected at least 4 sensor limit tests, got {len(sensor_limits)}"

    positions = {tc.metadata.get("position"): tc.inputs.get("temperature") for tc in sensor_limits}
    assert "min_limit" in positions and positions["min_limit"] == -20.0
    assert "below_min" in positions and positions["below_min"] == -21.0
    assert "max_limit" in positions and positions["max_limit"] == 120.0
    assert "above_max" in positions and positions["above_max"] == 121.0

    # Tests violating limits must assert safe outputs
    below_min_tc = next(tc for tc in sensor_limits if tc.metadata.get("position") == "below_min")
    assert below_min_tc.expected_outputs.get("FAN_PIN") == "LOW"
    assert below_min_tc.priority == TestPriority.CRITICAL

    above_max_tc = next(tc for tc in sensor_limits if tc.metadata.get("position") == "above_max")
    assert above_max_tc.expected_outputs.get("FAN_PIN") == "LOW"
    assert above_max_tc.priority == TestPriority.CRITICAL


def test_4_sensor_failure_test_is_generated(fan_controller_suite: TestSuite):
    """4. Verify sensor failure test is generated because firmware documents sensor fault handling."""
    failure_tests = fan_controller_suite.filter_by_category(TestCategory.SENSOR_FAILURE)
    assert len(failure_tests) >= 1, "Expected at least 1 SENSOR_FAILURE test"

    tc = failure_tests[0]
    assert tc.priority == TestPriority.CRITICAL
    assert "temperature" in tc.inputs or "sensor_connected" in tc.inputs
    assert tc.expected_outputs.get("FAN_PIN") == "LOW"
    assert "SENSOR_DISCONNECTED" in (tc.expected_serial_log or "")
    assert "SYSTEM_SENSOR_FAULT" in tc.expected_behavior


def test_5_state_transition_tests_are_generated(fan_controller_suite: TestSuite, fan_controller_analysis: FirmwareAnalysis):
    """5. Verify state transition tests are generated for all documented transitions."""
    state_tests = fan_controller_suite.filter_by_category(TestCategory.STATE_TRANSITION)
    assert len(state_tests) == len(fan_controller_analysis.state_transitions), (
        f"Expected {len(fan_controller_analysis.state_transitions)} transition tests, got {len(state_tests)}"
    )

    tested_transitions = {(tc.metadata["from_state"], tc.metadata["to_state"]) for tc in state_tests}
    for st in fan_controller_analysis.state_transitions:
        pair = (st.from_state, st.to_state)
        assert pair in tested_transitions, f"State transition {pair} not covered by test suite"


def test_6_communication_tests_not_generated_when_no_failure_behavior(fan_controller_suite: TestSuite):
    """
    6. Verify communication tests are NOT generated when no communication failure behavior exists,
    and ARE generated when communication failure behavior is explicitly documented.
    """
    # Fan controller only has UART for printf logging and NO comm failure behavior
    fan_comm_tests = fan_controller_suite.filter_by_category(TestCategory.COMMUNICATION_FAILURE)
    assert len(fan_comm_tests) == 0, (
        f"Fan controller should NOT have COMMUNICATION_FAILURE tests, found {len(fan_comm_tests)}"
    )

    # Now verify that when comm failure behavior DOES exist, tests ARE generated
    analysis_with_comm_failure = FirmwareAnalysis(
        firmware_name="telemetry_fw",
        target_hardware=TargetHardware(board="esp32-devkit-c"),
        language="C",
        communication_interfaces=[
            CommunicationInterface(interface_type="UART", identifier="UART1", baud_rate=115200)
        ],
        error_handling=[
            ErrorHandlingRule(
                error_id="ERR_COMM_TIMEOUT",
                fault_type="communication_failure",
                trigger_condition="uart_timeout_ms > 2000",
                mitigation_action="Enter fail-safe and log bus error",
                safe_state="COMM_FAULT_STATE"
            )
        ]
    )
    comm_suite = generate_tests(analysis_with_comm_failure)
    gen_comm_tests = comm_suite.filter_by_category(TestCategory.COMMUNICATION_FAILURE)
    assert len(gen_comm_tests) >= 1, "Expected communication failure test when error rule is present"
    assert gen_comm_tests[0].category == TestCategory.COMMUNICATION_FAILURE
    assert "UART" in gen_comm_tests[0].name


def test_7_generated_test_ids_are_unique(fan_controller_suite: TestSuite):
    """7. Verify all generated test IDs are unique across the entire TestSuite."""
    all_ids = [tc.id for tc in fan_controller_suite.test_cases]
    assert len(all_ids) > 0
    unique_ids = set(all_ids)
    assert len(all_ids) == len(unique_ids), f"Duplicate test IDs found: {len(all_ids) - len(unique_ids)} duplicates"


def test_8_every_generated_test_case_passes_pydantic_validation(fan_controller_suite: TestSuite):
    """8. Verify every generated TestCase passes strict Pydantic validation and has all required fields."""
    required_fields = [
        "id",
        "name",
        "category",
        "description",
        "priority",
        "preconditions",
        "inputs",
        "actions",
        "expected_outputs",
        "expected_behavior",
        "failure_conditions",
        "hardware_requirements",
    ]

    for tc in fan_controller_suite.test_cases:
        # Verify it is an instance of TestCase
        assert isinstance(tc, TestCase)

        # Validate dump round-trip
        data = tc.model_dump()
        revalidated = TestCase.model_validate(data)
        assert revalidated.id == tc.id

        # Verify all 12 required fields are populated
        for field in required_fields:
            val = getattr(tc, field)
            assert val is not None, f"Field '{field}' is None in test case {tc.id}"
            if isinstance(val, (list, dict)):
                # preconditions, actions, failure_conditions must not be empty
                if field in ["actions", "failure_conditions"]:
                    assert len(val) > 0, f"Field '{field}' is empty list in test case {tc.id}"


def test_9_no_duplicate_tests_are_generated(fan_controller_suite: TestSuite):
    """9. Verify no duplicate tests exist in the generated TestSuite."""
    seen_names = set()
    seen_signatures = set()

    for tc in fan_controller_suite.test_cases:
        # Check name uniqueness
        assert tc.name not in seen_names, f"Duplicate test name found: '{tc.name}'"
        seen_names.add(tc.name)

        # Check signature uniqueness (category + input signature)
        input_sig = str(sorted(tc.inputs.items())) if tc.inputs else ""
        sig = (tc.category.value, tc.name, input_sig)
        assert sig not in seen_signatures, f"Duplicate test signature found: {sig}"
        seen_signatures.add(sig)


def test_10_generator_works_with_minimal_firmware_analysis():
    """10. Verify generator works gracefully with minimal FirmwareAnalysis (no crashes, valid suite)."""
    minimal_analysis = FirmwareAnalysis(
        firmware_name="bare_bones_fw",
        target_hardware="arduino-uno",
        language="C"
    )

    generator = DeterministicTestGenerator(minimal_analysis)
    suite = generator.generate()

    assert isinstance(suite, TestSuite)
    assert suite.firmware_name == "bare_bones_fw"
    assert suite.target_hardware == "arduino-uno"
    assert suite.total_tests >= 1  # Base boot test generated

    # Verify all generated tests in minimal suite validate cleanly
    for tc in suite.test_cases:
        assert isinstance(tc, TestCase)
        assert tc.id.startswith("TC_")
        assert tc.hardware_requirements["board"] == "arduino-uno"
