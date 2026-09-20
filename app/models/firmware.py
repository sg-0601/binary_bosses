"""
Firmware Analysis Data Models
Structured representation of firmware analysis extracted by AI or static analysis tools.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class TargetHardware(BaseModel):
    board: str = Field(..., description="Target development board (e.g. 'esp32-devkit-c', 'arduino-uno')")
    mcu: Optional[str] = Field(None, description="Microcontroller model/family (e.g. 'ESP32', 'ATmega328P')")
    architecture: Optional[str] = Field(None, description="Processor architecture (e.g. 'Xtensa LX6', 'AVR', 'ARM Cortex-M4')")
    operating_voltage: Optional[str] = Field(None, description="Operating voltage (e.g. '3.3V', '5V')")
    clock_frequency_mhz: Optional[float] = Field(None, description="Clock frequency in MHz")
    notes: Optional[str] = Field(None, description="Hardware-specific notes or constraints")


class HardwareInput(BaseModel):
    name: str = Field(..., description="Logical or identifier name for the input (e.g. 'temp_sensor_pin')")
    pin: Optional[str] = Field(None, description="Physical pin number or designation (e.g. '34', 'A0', 'GPIO_4')")
    input_type: str = Field(..., description="Type of input: 'analog', 'digital', 'interrupt', 'serial', 'virtual'")
    signal_type: Optional[str] = Field(None, description="Signal characteristics (e.g. 'voltage', 'current', 'pulse')")
    active_level: Optional[str] = Field(None, description="Active level: 'HIGH', 'LOW', 'CONTINUOUS'")
    pull_resistor: Optional[str] = Field(None, description="Internal pull resistor setting: 'none', 'pullup', 'pulldown'")
    description: Optional[str] = Field(None, description="Description of input purpose and connection")


class HardwareOutput(BaseModel):
    name: str = Field(..., description="Logical or identifier name for the output (e.g. 'FAN_PIN', 'STATUS_LED')")
    pin: Optional[str] = Field(None, description="Physical pin number or designation (e.g. '13', 'GPIO_12')")
    output_type: str = Field(..., description="Output type: 'digital', 'pwm', 'analog', 'dac'")
    default_state: Optional[str] = Field(None, description="Default or initial state ('LOW', 'HIGH', '0%')")
    active_level: Optional[str] = Field(None, description="Active assertion level: 'HIGH', 'LOW'")
    safe_state: Optional[str] = Field(None, description="Safe state during shutdown or fault condition (e.g. 'LOW', 'OFF')")
    description: Optional[str] = Field(None, description="Description of the controlled device or signal")


class Sensor(BaseModel):
    name: str = Field(..., description="Sensor name or model (e.g. 'Industrial Temperature Sensor', 'DHT22')")
    sensor_type: str = Field(..., description="Physical measurement type: 'temperature', 'humidity', 'pressure', 'voltage'")
    interface: str = Field(..., description="Interface used: 'analog_adc', 'i2c', 'spi', 'onewire', 'gpio_pulse'")
    pin_or_bus: Optional[str] = Field(None, description="Associated pin or bus address (e.g. 'A0', '0x48')")
    unit: str = Field(..., description="Measurement unit (e.g. 'Celsius', 'C', 'V', 'kPa')")
    min_operational_value: Optional[float] = Field(None, description="Minimum normal operational value")
    max_operational_value: Optional[float] = Field(None, description="Maximum normal operational value")
    sampling_interval_ms: Optional[float] = Field(None, description="Typical sampling interval in milliseconds")
    description: Optional[str] = Field(None, description="Sensor role, behavior, and physical placement")


class Actuator(BaseModel):
    name: str = Field(..., description="Actuator name (e.g. 'Cooling Fan Relay', 'Buzzer')")
    actuator_type: str = Field(..., description="Actuator category: 'relay', 'motor', 'led', 'valve', 'heater'")
    control_pin: Optional[str] = Field(None, description="Pin driving the actuator (e.g. '13')")
    control_type: str = Field(default="digital", description="Control modality: 'digital', 'pwm', 'dac', 'stepper'")
    active_state: str = Field(default="HIGH", description="Value that engages actuator ('HIGH', 'LOW', '>0%')")
    safe_state: str = Field(default="OFF", description="Safe/de-energized state ('OFF', 'LOW', '0%')")
    description: Optional[str] = Field(None, description="Actuator role and physical consequence")


class Peripheral(BaseModel):
    name: str = Field(..., description="Peripheral component name (e.g. 'GPIO', 'Timer0', 'ADC1')")
    peripheral_type: str = Field(..., description="Type of peripheral: 'gpio', 'adc', 'timer', 'pwm', 'uart', 'watchdog'")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Key configuration parameters")
    description: Optional[str] = Field(None, description="How the peripheral is used by the firmware")


class CommunicationInterface(BaseModel):
    interface_type: str = Field(..., description="Interface standard: 'UART', 'I2C', 'SPI', 'CAN', 'BLE', 'WiFi'")
    identifier: Optional[str] = Field(None, description="Port/bus identifier (e.g. 'UART0', 'Serial')")
    baud_rate: Optional[int] = Field(None, description="Baud rate if applicable (e.g. 115200, 9600)")
    pins: Dict[str, str] = Field(default_factory=dict, description="Interface pin assignments (e.g. {'TX': '1', 'RX': '3'})")
    protocol_details: Optional[str] = Field(None, description="Framing, message format, or protocol details")
    description: Optional[str] = Field(None, description="Role of the communication interface in the firmware")


class ImportantCondition(BaseModel):
    condition_id: str = Field(..., description="Unique condition identifier (e.g. 'COND_HIGH_TEMP_ACTIVE')")
    description: str = Field(..., description="Human-readable explanation of the condition")
    trigger: str = Field(..., description="Logic/expression triggering this condition (e.g. 'temp > 30.0')")
    expected_action: str = Field(..., description="Expected system response (e.g. 'set_fan(true)')")
    priority: str = Field(default="normal", description="Priority level: 'critical', 'high', 'normal', 'low'")


class BoundaryCondition(BaseModel):
    parameter: str = Field(..., description="Monitored parameter or variable name (e.g. 'temperature')")
    threshold: Optional[float] = Field(None, description="Critical decision threshold value (e.g. 30.0)")
    min_limit: Optional[float] = Field(None, description="Minimum acceptable or valid limit (e.g. -20.0)")
    max_limit: Optional[float] = Field(None, description="Maximum acceptable or valid limit (e.g. 120.0)")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g. 'Celsius', 'C')")
    behavior_at_or_below: Optional[str] = Field(None, description="System behavior at or below threshold/min limit")
    behavior_above: Optional[str] = Field(None, description="System behavior above threshold/max limit")
    edge_case_notes: Optional[str] = Field(None, description="Notes on boundary equality, float precision, or edge behavior")


class ErrorHandlingRule(BaseModel):
    error_id: str = Field(..., description="Error condition ID (e.g. 'ERR_SENSOR_FAULT')")
    fault_type: str = Field(..., description="Classification: 'sensor_fault', 'communication_loss', 'out_of_range', 'hardware_fault'")
    trigger_condition: str = Field(..., description="Condition causing this error (e.g. 'temp < -20.0 || temp > 120.0')")
    mitigation_action: str = Field(..., description="Immediate mitigation or fail-safe action (e.g. 'Turn fan OFF')")
    safe_state: Optional[str] = Field(None, description="Safe state entered (e.g. 'SYSTEM_SENSOR_FAULT')")
    alert_channel: Optional[str] = Field(None, description="Reporting mechanism (e.g. 'UART serial log')")
    recovery: Optional[str] = Field(None, description="Recovery policy (e.g. 'Automatic upon valid input' or 'Latch until reboot')")


class FirmwareState(BaseModel):
    name: str = Field(..., description="State name / enum identifier (e.g. 'SYSTEM_INIT', 'SYSTEM_FAN_ACTIVE')")
    enum_value: Optional[int] = Field(None, description="Integer value if defined in enum")
    description: str = Field(..., description="Functional description of what occurs in this state")
    is_initial: bool = Field(default=False, description="True if system starts in this state")
    is_error_state: bool = Field(default=False, description="True if this is an error or fail-safe state")
    expected_outputs: Dict[str, str] = Field(default_factory=dict, description="Expected state of outputs in this state")


class StateTransition(BaseModel):
    from_state: str = Field(..., description="Source state name")
    to_state: str = Field(..., description="Target destination state name")
    trigger: str = Field(..., description="Event or condition initiating transition")
    guard_condition: Optional[str] = Field(None, description="Prerequisite conditions that must evaluate true")
    action_on_transition: Optional[str] = Field(None, description="Actions or output changes executed upon transition")
    description: Optional[str] = Field(None, description="Contextual description of the transition")


class TimingRequirement(BaseModel):
    name: str = Field(..., description="Timing aspect name (e.g. 'sensor_sample_rate', 'fan_switching_latency')")
    timing_type: str = Field(..., description="Category: 'periodic', 'delay', 'timeout', 'response_time', 'watchdog'")
    duration_ms: Optional[float] = Field(None, description="Duration, period, or timeout in milliseconds")
    tolerance_ms: Optional[float] = Field(None, description="Acceptable tolerance or jitter in ms")
    description: str = Field(..., description="Description of the timing requirement")


class TimingBehavior(BaseModel):
    execution_model: str = Field(default="synchronous", description="Execution paradigm: 'synchronous', 'polled_loop', 'interrupt_driven', 'rtos'")
    sampling_interval_ms: Optional[float] = Field(None, description="Default sampling or tick interval in milliseconds")
    response_time_ms: Optional[float] = Field(None, description="Expected system response latency in milliseconds")
    watchdog_timeout_ms: Optional[float] = Field(None, description="Watchdog timer period in ms if configured")
    requirements: List[TimingRequirement] = Field(default_factory=list, description="Specific timing requirements")
    description: Optional[str] = Field(None, description="Summary of firmware timing dynamics")


class Assumption(BaseModel):
    id: str = Field(..., description="Assumption identifier (e.g. 'ASM_01')")
    category: str = Field(default="hardware", description="Category: 'hardware', 'environment', 'electrical', 'timing', 'software'")
    statement: str = Field(..., description="Explicit assumption made by the firmware or operating environment")
    impact_if_violated: Optional[str] = Field(None, description="Consequence if this assumption does not hold")


class TestableBehavior(BaseModel):
    __test__ = False
    id: str = Field(..., description="Identifier for testable behavior (e.g. 'TB_01')")
    name: str = Field(..., description="Short descriptive name")
    category: str = Field(default="functional", description="Test category: 'functional', 'boundary', 'fault_tolerance', 'timing'")
    description: str = Field(..., description="Comprehensive behavior description")
    preconditions: List[str] = Field(default_factory=list, description="Preconditions or initial state required")
    stimulus: str = Field(..., description="Input condition or stimulus provided to firmware")
    expected_state: Optional[str] = Field(None, description="Expected resulting system state")
    expected_outputs: Dict[str, Any] = Field(default_factory=dict, description="Expected pin or actuator values")
    expected_serial_log: Optional[str] = Field(None, description="Expected serial monitor text / pattern")
    verification_criteria: Optional[str] = Field(None, description="How the behavior is verified")


class FirmwareAnalysis(BaseModel):
    """
    Complete structured firmware analysis model containing all components,
    state machines, boundaries, timing, and testable behaviors.
    """
    firmware_name: str = Field(..., description="Name or title of the analyzed firmware")
    target_hardware: TargetHardware = Field(..., description="Hardware platform and microcontroller details")
    language: str = Field(..., description="Programming language of the firmware (e.g. 'C', 'C++', 'Arduino C++')")
    inputs: List[HardwareInput] = Field(default_factory=list, description="Firmware inputs (pins, signals, readings)")
    outputs: List[HardwareOutput] = Field(default_factory=list, description="Firmware outputs (pins, indicators, drivers)")
    sensors: List[Sensor] = Field(default_factory=list, description="Sensors connected to or read by firmware")
    actuators: List[Actuator] = Field(default_factory=list, description="Actuators operated by firmware")
    peripherals: List[Peripheral] = Field(default_factory=list, description="Microcontroller peripherals utilized")
    communication_interfaces: List[CommunicationInterface] = Field(default_factory=list, description="Serial/bus communication channels")
    important_conditions: List[ImportantCondition] = Field(default_factory=list, description="Core business logic conditions and rules")
    boundary_conditions: List[BoundaryCondition] = Field(default_factory=list, description="Threshold limits and edge-case boundaries")
    error_handling: List[ErrorHandlingRule] = Field(default_factory=list, description="Fault detection, error mitigation, and safe states")
    states: List[FirmwareState] = Field(default_factory=list, description="Finite state machine states")
    state_transitions: List[StateTransition] = Field(default_factory=list, description="Allowed transitions between FSM states")
    timing_behavior: TimingBehavior = Field(default_factory=TimingBehavior, description="Timing, loop rates, and responsiveness")
    assumptions: List[Assumption] = Field(default_factory=list, description="Hardware, environment, and electrical assumptions")
    testable_behaviors: List[TestableBehavior] = Field(default_factory=list, description="Discrete testable behaviors for test generation")

    @field_validator("target_hardware", mode="before")
    @classmethod
    def _coerce_target_hardware(cls, v: Any) -> Any:
        if isinstance(v, str):
            return {"board": v}
        return v

    @field_validator("timing_behavior", mode="before")
    @classmethod
    def _coerce_timing_behavior(cls, v: Any) -> Any:
        if isinstance(v, list):
            return {"requirements": v}
        return v

    @field_validator("assumptions", mode="before")
    @classmethod
    def _coerce_assumptions(cls, v: Any) -> Any:
        if isinstance(v, list):
            coerced = []
            for idx, item in enumerate(v, start=1):
                if isinstance(item, str):
                    coerced.append({"id": f"ASM_{idx:02d}", "statement": item})
                else:
                    coerced.append(item)
            return coerced
        return v

    def get_testable_behavior(self, behavior_id: str) -> Optional[TestableBehavior]:
        """Find a testable behavior by ID (e.g. 'TB_01')."""
        for tb in self.testable_behaviors:
            if tb.id == behavior_id:
                return tb
        return None

    def get_state(self, state_name: str) -> Optional[FirmwareState]:
        """Find a state by name."""
        for state in self.states:
            if state.name == state_name:
                return state
        return None

    def get_transitions_from(self, state_name: str) -> List[StateTransition]:
        """Get all transitions originating from a given state."""
        return [t for t in self.state_transitions if t.from_state == state_name]

    def get_error_handling(self, error_id: str) -> Optional[ErrorHandlingRule]:
        """Find error handling rule by ID."""
        for err in self.error_handling:
            if err.error_id == error_id:
                return err
        return None

    def to_json_file(self, file_path: Union[str, Path], indent: int = 2) -> None:
        """Serialize firmware analysis model to JSON file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=indent))

    @classmethod
    def from_json_file(cls, file_path: Union[str, Path]) -> "FirmwareAnalysis":
        """Load and validate firmware analysis model from a JSON file."""
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())
