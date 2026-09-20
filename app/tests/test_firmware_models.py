import json
import pytest
from pathlib import Path
from pydantic import ValidationError

from app.models.firmware import (
    FirmwareAnalysis,
    TargetHardware,
    HardwareInput,
    HardwareOutput,
    Sensor,
    Actuator,
    Peripheral,
    CommunicationInterface,
    ImportantCondition,
    BoundaryCondition,
    ErrorHandlingRule,
    FirmwareState,
    StateTransition,
    TimingRequirement,
    TimingBehavior,
    Assumption,
    TestableBehavior,
)
from app.utils.config import settings


def test_firmware_analysis_minimal_instantiation():
    """Verify minimal valid FirmwareAnalysis instance with defaults."""
    analysis = FirmwareAnalysis(
        firmware_name="minimal_fw",
        target_hardware=TargetHardware(board="arduino-uno"),
        language="C"
    )

    assert analysis.firmware_name == "minimal_fw"
    assert analysis.target_hardware.board == "arduino-uno"
    assert analysis.language == "C"
    assert analysis.inputs == []
    assert analysis.outputs == []
    assert analysis.sensors == []
    assert analysis.actuators == []
    assert analysis.peripherals == []
    assert analysis.communication_interfaces == []
    assert analysis.important_conditions == []
    assert analysis.boundary_conditions == []
    assert analysis.error_handling == []
    assert analysis.states == []
    assert analysis.state_transitions == []
    assert isinstance(analysis.timing_behavior, TimingBehavior)
    assert analysis.assumptions == []
    assert analysis.testable_behaviors == []


def test_all_17_fields_present_and_structured():
    """Verify all 17 specified fields exist, are structured, and serialize correctly."""
    required_fields = [
        "firmware_name",
        "target_hardware",
        "language",
        "inputs",
        "outputs",
        "sensors",
        "actuators",
        "peripherals",
        "communication_interfaces",
        "important_conditions",
        "boundary_conditions",
        "error_handling",
        "states",
        "state_transitions",
        "timing_behavior",
        "assumptions",
        "testable_behaviors",
    ]

    analysis = FirmwareAnalysis(
        firmware_name="test_fw",
        target_hardware={"board": "esp32-devkit-c", "mcu": "ESP32"},
        language="C++",
        inputs=[{"name": "btn", "pin": "0", "input_type": "digital"}],
        outputs=[{"name": "led", "pin": "2", "output_type": "digital"}],
        sensors=[{"name": "pot", "sensor_type": "voltage", "interface": "analog_adc", "unit": "V"}],
        actuators=[{"name": "buzzer", "actuator_type": "buzzer", "control_pin": "5"}],
        peripherals=[{"name": "GPIO", "peripheral_type": "gpio"}],
        communication_interfaces=[{"interface_type": "UART", "baud_rate": 115200}],
        important_conditions=[{"condition_id": "C1", "description": "d", "trigger": "t", "expected_action": "a"}],
        boundary_conditions=[{"parameter": "p", "threshold": 10.0}],
        error_handling=[{"error_id": "E1", "fault_type": "f", "trigger_condition": "tc", "mitigation_action": "ma"}],
        states=[{"name": "IDLE", "description": "Idle state"}],
        state_transitions=[{"from_state": "IDLE", "to_state": "RUN", "trigger": "btn_pressed"}],
        timing_behavior={"sampling_interval_ms": 50.0},
        assumptions=[{"id": "A1", "statement": "stable power"}],
        testable_behaviors=[{"id": "TB_01", "name": "boot", "description": "desc", "stimulus": "reset"}]
    )

    data = analysis.model_dump()
    for field in required_fields:
        assert field in data, f"Field '{field}' missing from FirmwareAnalysis model"

    # Confirm structured types rather than flat text
    assert isinstance(data["target_hardware"], dict)
    assert isinstance(data["inputs"], list) and isinstance(data["inputs"][0], dict)
    assert isinstance(data["outputs"], list) and isinstance(data["outputs"][0], dict)
    assert isinstance(data["sensors"], list) and isinstance(data["sensors"][0], dict)
    assert isinstance(data["actuators"], list) and isinstance(data["actuators"][0], dict)
    assert isinstance(data["peripherals"], list) and isinstance(data["peripherals"][0], dict)
    assert isinstance(data["communication_interfaces"], list) and isinstance(data["communication_interfaces"][0], dict)
    assert isinstance(data["important_conditions"], list) and isinstance(data["important_conditions"][0], dict)
    assert isinstance(data["boundary_conditions"], list) and isinstance(data["boundary_conditions"][0], dict)
    assert isinstance(data["error_handling"], list) and isinstance(data["error_handling"][0], dict)
    assert isinstance(data["states"], list) and isinstance(data["states"][0], dict)
    assert isinstance(data["state_transitions"], list) and isinstance(data["state_transitions"][0], dict)
    assert isinstance(data["timing_behavior"], dict)
    assert isinstance(data["assumptions"], list) and isinstance(data["assumptions"][0], dict)
    assert isinstance(data["testable_behaviors"], list) and isinstance(data["testable_behaviors"][0], dict)


def test_target_hardware_string_coercion():
    """Verify string input for target_hardware auto-coerces to TargetHardware model."""
    analysis = FirmwareAnalysis(
        firmware_name="board_test",
        target_hardware="esp32-devkit-c",
        language="C"
    )
    assert isinstance(analysis.target_hardware, TargetHardware)
    assert analysis.target_hardware.board == "esp32-devkit-c"


def test_timing_behavior_list_coercion():
    """Verify list of timing requirements coerces into TimingBehavior."""
    requirements = [
        {"name": "poll", "timing_type": "periodic", "duration_ms": 100.0, "description": "Poll rate"}
    ]
    analysis = FirmwareAnalysis(
        firmware_name="timing_test",
        target_hardware="esp32-devkit-c",
        language="C",
        timing_behavior=requirements
    )
    assert isinstance(analysis.timing_behavior, TimingBehavior)
    assert len(analysis.timing_behavior.requirements) == 1
    assert analysis.timing_behavior.requirements[0].name == "poll"


def test_assumptions_string_list_coercion():
    """Verify passing string list to assumptions auto-creates Assumption models."""
    analysis = FirmwareAnalysis(
        firmware_name="asm_test",
        target_hardware="esp32-devkit-c",
        language="C",
        assumptions=["Power supply is regulated at 3.3V", "Crystal oscillator is 40MHz"]
    )
    assert len(analysis.assumptions) == 2
    assert analysis.assumptions[0].id == "ASM_01"
    assert "3.3V" in analysis.assumptions[0].statement
    assert analysis.assumptions[1].id == "ASM_02"


def test_fan_controller_example_json_validation():
    """Validate example JSON file for fan_controller against FirmwareAnalysis model."""
    json_path = settings.PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "firmware_analysis.json"
    assert json_path.exists(), f"Example JSON file not found at {json_path}"

    analysis = FirmwareAnalysis.from_json_file(json_path)

    # Validate high-level metadata
    assert analysis.firmware_name == "fan_controller"
    assert analysis.target_hardware.board == "esp32-devkit-c"
    assert analysis.target_hardware.mcu == "ESP32"
    assert analysis.language == "C"

    # Validate inputs & outputs
    assert len(analysis.inputs) >= 1
    assert analysis.inputs[0].name == "temperature_reading"
    assert len(analysis.outputs) >= 2
    output_pins = {o.pin: o.name for o in analysis.outputs}
    assert "13" in output_pins
    assert output_pins["13"] == "FAN_PIN"

    # Validate sensors & actuators
    assert len(analysis.sensors) == 1
    assert analysis.sensors[0].sensor_type == "temperature"
    assert analysis.sensors[0].min_operational_value == -20.0
    assert analysis.sensors[0].max_operational_value == 120.0

    assert len(analysis.actuators) == 1
    assert analysis.actuators[0].control_pin == "13"
    assert analysis.actuators[0].safe_state == "OFF"

    # Validate peripherals & communication
    periph_types = [p.peripheral_type for p in analysis.peripherals]
    assert "gpio" in periph_types
    assert "uart" in periph_types
    assert len(analysis.communication_interfaces) >= 1
    assert analysis.communication_interfaces[0].baud_rate == 115200

    # Validate conditions & boundaries
    assert len(analysis.important_conditions) == 3
    cond_ids = [c.condition_id for c in analysis.important_conditions]
    assert "COND_HIGH_TEMP_ACTIVE" in cond_ids

    assert len(analysis.boundary_conditions) >= 3
    temp_boundary = next(b for b in analysis.boundary_conditions if b.threshold == 30.0)
    assert temp_boundary.unit == "Celsius"

    # Validate error handling
    assert len(analysis.error_handling) >= 1
    err = analysis.get_error_handling("ERR_SENSOR_DISCONNECTED")
    assert err is not None
    assert err.safe_state == "SYSTEM_SENSOR_FAULT"

    # Validate state machine
    state_names = [s.name for s in analysis.states]
    assert "SYSTEM_INIT" in state_names
    assert "SYSTEM_NORMAL_COOLING" in state_names
    assert "SYSTEM_FAN_ACTIVE" in state_names
    assert "SYSTEM_SENSOR_FAULT" in state_names
    assert analysis.get_state("SYSTEM_INIT").is_initial is True
    assert analysis.get_state("SYSTEM_SENSOR_FAULT").is_error_state is True

    # Validate transitions
    normal_transitions = analysis.get_transitions_from("SYSTEM_NORMAL_COOLING")
    assert len(normal_transitions) == 2
    destinations = [t.to_state for t in normal_transitions]
    assert "SYSTEM_FAN_ACTIVE" in destinations
    assert "SYSTEM_SENSOR_FAULT" in destinations

    # Validate timing
    assert analysis.timing_behavior.sampling_interval_ms == 1000.0
    assert len(analysis.timing_behavior.requirements) >= 2

    # Validate testable behaviors
    assert len(analysis.testable_behaviors) >= 5
    tb_03 = analysis.get_testable_behavior("TB_03")
    assert tb_03 is not None
    assert "Fan: ON" in tb_03.expected_serial_log
    assert tb_03.expected_state == "SYSTEM_FAN_ACTIVE"

    tb_05 = analysis.get_testable_behavior("TB_05")
    assert tb_05 is not None
    assert "SENSOR_DISCONNECTED" in tb_05.expected_serial_log
    assert tb_05.expected_state == "SYSTEM_SENSOR_FAULT"


def test_roundtrip_file_serialization(tmp_path):
    """Verify serializing to a file and deserializing back yields equal models."""
    json_path = settings.PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "firmware_analysis.json"
    original = FirmwareAnalysis.from_json_file(json_path)

    temp_file = tmp_path / "dumped_analysis.json"
    original.to_json_file(temp_file)

    loaded = FirmwareAnalysis.from_json_file(temp_file)
    assert original.model_dump() == loaded.model_dump()


def test_validation_errors():
    """Verify ValidationError on missing required fields or invalid types."""
    with pytest.raises(ValidationError):
        # Missing firmware_name, target_hardware, language
        FirmwareAnalysis.model_validate({})

    with pytest.raises(ValidationError):
        # Invalid clock_frequency_mhz (string instead of float)
        FirmwareAnalysis(
            firmware_name="bad_fw",
            target_hardware=TargetHardware(board="test", clock_frequency_mhz="not-a-number"),
            language="C"
        )
