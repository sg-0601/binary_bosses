"""
Deterministic Firmware Test Generator
Generates comprehensive, categorized TestSuite from structured FirmwareAnalysis.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from app.models.firmware import FirmwareAnalysis, BoundaryCondition, StateTransition, Sensor
from app.models.test_case import TestCase, TestSuite, TestCategory, TestPriority


class DeterministicTestGenerator:
    """
    Analyzes structured FirmwareAnalysis and deterministically produces
    a comprehensive TestSuite across all 8 standard verification categories.
    """

    def __init__(self, analysis: FirmwareAnalysis):
        self.analysis = analysis
        self.counters: Dict[str, int] = {
            "NORM": 0,
            "BOUND": 0,
            "ABNORM": 0,
            "FAIL": 0,
            "STATE": 0,
            "COMM": 0,
            "UNEXP": 0,
            "COMB": 0,
        }
        self.seen_signatures: Set[Tuple[str, str, str]] = set()
        self.seen_boundaries: Set[Tuple[str, float]] = set()

    def generate(self) -> TestSuite:
        """Execute test generation and return complete TestSuite."""
        suite = TestSuite(
            firmware_name=self.analysis.firmware_name,
            target_hardware=self.analysis.target_hardware.board,
        )

        # 1. NORMAL: Normal operational conditions and boot
        self._generate_normal_tests(suite)

        # 2. BOUNDARY: Threshold boundaries and sensor limit boundaries
        self._generate_boundary_tests(suite)

        # 3. ABNORMAL: Invalid, out-of-scale, or extreme inputs
        self._generate_abnormal_tests(suite)

        # 4. SENSOR_FAILURE: Sensor disconnection and hardware faults
        self._generate_sensor_failure_tests(suite)

        # 5. STATE_TRANSITION: All documented FSM transitions
        self._generate_state_transition_tests(suite)

        # 6. COMMUNICATION_FAILURE: Only when communication failure behavior exists
        self._generate_communication_failure_tests(suite)

        # 7. UNEXPECTED_INPUT: Supported unexpected conditions (jitter, floating)
        self._generate_unexpected_input_tests(suite)

        # 8. COMBINATION: High-value combinations without combinatorial explosion
        self._generate_combination_tests(suite)

        return suite

    def _next_id(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"TC_{prefix}_{self.counters[prefix]:03d}"

    def _add_test_case(self, suite: TestSuite, tc: TestCase) -> bool:
        """Add test case to suite if not duplicate based on signature."""
        input_key = str(sorted(tc.inputs.items())) if tc.inputs else ""
        sig = (tc.category.value, tc.name, input_key)
        if sig in self.seen_signatures:
            return False
        self.seen_signatures.add(sig)
        suite.add_test_case(tc)
        return True

    def _normalize_param_name(self, param: str) -> str:
        """Normalize parameter name to base physical quantity (e.g. temperature)."""
        for sensor in self.analysis.sensors:
            if sensor.sensor_type in param or param in sensor.sensor_type:
                return sensor.sensor_type
        for suffix in ["_lower_sensor_limit", "_upper_sensor_limit", "_limit", "_threshold", "_min", "_max"]:
            if param.endswith(suffix):
                return param[:-len(suffix)]
        return param

    def _build_hardware_requirements(self, pins: Optional[List[str]] = None) -> Dict[str, Any]:
        """Construct hardware requirements dict for test case."""
        req_pins: List[str] = []
        if pins:
            req_pins = list(pins)
        else:
            for inp in self.analysis.inputs:
                if inp.pin and inp.pin not in req_pins:
                    req_pins.append(inp.pin)
            for out in self.analysis.outputs:
                if out.pin and out.pin not in req_pins:
                    req_pins.append(out.pin)

        return {
            "board": self.analysis.target_hardware.board,
            "mcu": self.analysis.target_hardware.mcu or "generic",
            "architecture": self.analysis.target_hardware.architecture or "generic",
            "required_pins": req_pins,
        }

    def _get_safe_outputs(self) -> Dict[str, Any]:
        """Resolve expected safe outputs."""
        outputs: Dict[str, Any] = {}
        for out in self.analysis.outputs:
            outputs[out.name] = out.safe_state or out.default_state or "LOW"
        for state in self.analysis.states:
            if state.is_error_state and state.expected_outputs:
                outputs.update(state.expected_outputs)
        return outputs

    def _get_normal_outputs(self) -> Dict[str, Any]:
        """Resolve expected outputs under normal cooling / idle operation."""
        outputs: Dict[str, Any] = {}
        for out in self.analysis.outputs:
            outputs[out.name] = out.default_state or "LOW"
        for state in self.analysis.states:
            if (state.is_initial or "normal" in state.name.lower() or "idle" in state.name.lower()) and state.expected_outputs:
                outputs.update(state.expected_outputs)
        return outputs

    def _get_active_outputs(self) -> Dict[str, Any]:
        """Resolve expected outputs under active state."""
        outputs: Dict[str, Any] = {}
        for out in self.analysis.outputs:
            outputs[out.name] = out.active_level or "HIGH"
        for state in self.analysis.states:
            if not state.is_initial and not state.is_error_state and state.expected_outputs:
                outputs.update(state.expected_outputs)
        return outputs

    # =========================================================================
    # 1. NORMAL TESTS
    # =========================================================================
    def _generate_normal_tests(self, suite: TestSuite) -> None:
        # Boot / Initialization test
        boot_state = next((s for s in self.analysis.states if s.is_initial), None)
        boot_outputs = boot_state.expected_outputs if boot_state else self._get_normal_outputs()
        boot_log = next(
            (tb.expected_serial_log for tb in self.analysis.testable_behaviors if "boot" in tb.name.lower() or "init" in tb.name.lower()),
            "[SYSTEM_BOOT]"
        )

        tc_boot = TestCase(
            id=self._next_id("NORM"),
            name="System Boot and Hardware Initialization",
            category=TestCategory.NORMAL,
            description="Verify target microcontroller boots cleanly, initializes peripherals, and settles into initial state.",
            priority=TestPriority.CRITICAL,
            preconditions=["Target hardware powered on or reset asserted"],
            inputs={"power": "ON", "reset_pin": "HIGH"},
            actions=[
                "Apply nominal operating voltage to board",
                "Release hardware reset line",
                "Observe boot diagnostics and startup log",
            ],
            expected_outputs=boot_outputs,
            expected_behavior=(
                f"Firmware transitions to initial state '{boot_state.name if boot_state else 'INIT'}' "
                "with default peripheral outputs asserted and boot announcement logged."
            ),
            failure_conditions=[
                "Microcontroller enters infinite loop or watchdog crash",
                "Initial outputs do not match default safe state",
                "Boot announcement missing from serial monitor",
            ],
            hardware_requirements=self._build_hardware_requirements(),
            expected_serial_log=boot_log,
            metadata={"test_type": "boot_initialization"},
        )
        self._add_test_case(suite, tc_boot)

        # Normal operational conditions from sensors
        for sensor in self.analysis.sensors:
            min_val = sensor.min_operational_value if sensor.min_operational_value is not None else 0.0
            max_val = sensor.max_operational_value if sensor.max_operational_value is not None else 100.0

            # Find operating threshold if available
            matching_bc = next((bc for bc in self.analysis.boundary_conditions if bc.threshold is not None), None)
            if matching_bc and matching_bc.threshold is not None:
                nominal_val = round(matching_bc.threshold - 5.0, 1)
                if nominal_val < min_val:
                    nominal_val = round((min_val + matching_bc.threshold) / 2.0, 1)
            else:
                nominal_val = round((min_val + max_val) / 2.0, 1)

            unit = sensor.unit or ""
            param = sensor.sensor_type

            tc_norm = TestCase(
                id=self._next_id("NORM"),
                name=f"Nominal Normal Operation: {param} at {nominal_val} {unit}",
                category=TestCategory.NORMAL,
                description=f"Validate firmware steady-state behavior under nominal {param} ({nominal_val} {unit}).",
                priority=TestPriority.HIGH,
                preconditions=["System booted successfully in normal operating state"],
                inputs={param: nominal_val, "unit": unit},
                actions=[
                    f"Inject steady nominal {param} reading of {nominal_val} {unit}",
                    "Allow sensor sampling cycle to execute",
                    "Verify actuator states and output telemetry",
                ],
                expected_outputs=self._get_normal_outputs(),
                expected_behavior=(
                    f"Firmware remains in normal operating state with {param} within nominal limits. "
                    "Outputs remain in inactive/cooling standby."
                ),
                failure_conditions=[
                    "System triggers false positive alarm or unexpected actuation",
                    "Firmware fails to sample or parse sensor input",
                ],
                hardware_requirements=self._build_hardware_requirements(),
                expected_serial_log="Normal Range",
                metadata={"sensor": sensor.name, "nominal_value": nominal_val},
            )
            self._add_test_case(suite, tc_norm)

    # =========================================================================
    # 2. BOUNDARY TESTS
    # =========================================================================
    def _generate_boundary_tests(self, suite: TestSuite) -> None:
        # A. Threshold boundaries (below, at, above)
        for bc in self.analysis.boundary_conditions:
            if bc.threshold is not None:
                thresh = float(bc.threshold)
                param = bc.parameter
                base_param = self._normalize_param_name(param)
                unit = bc.unit or ""
                delta = 1.0

                val_below = round(thresh - delta, 1)
                val_exact = round(thresh, 1)
                val_above = round(thresh + delta, 1)

                # 1. Immediately below threshold (e.g. 29.0 C)
                if (base_param, val_below) not in self.seen_boundaries:
                    self.seen_boundaries.add((base_param, val_below))
                    tc_below = TestCase(
                        id=self._next_id("BOUND"),
                        name=f"Threshold Boundary Below: {base_param} at {val_below} {unit}",
                        category=TestCategory.BOUNDARY,
                        description=f"Verify system behavior immediately below decision threshold ({thresh} {unit}).",
                        priority=TestPriority.HIGH,
                        preconditions=["System operational in normal monitoring state"],
                        inputs={base_param: val_below, "threshold": thresh, "unit": unit},
                        actions=[
                            f"Inject {base_param} input of {val_below} {unit} (1 {unit} below {thresh} {unit} threshold)",
                            "Execute control loop evaluation",
                        ],
                        expected_outputs=self._get_normal_outputs(),
                        expected_behavior=bc.behavior_at_or_below or f"Condition <= {thresh} holds; normal standby maintained.",
                        failure_conditions=[f"Actuator prematurely triggered below threshold at {val_below} {unit}"],
                        hardware_requirements=self._build_hardware_requirements(),
                        expected_serial_log="Normal Range",
                        metadata={"boundary_type": "threshold", "position": "below", "threshold": thresh, "value": val_below},
                    )
                    self._add_test_case(suite, tc_below)

                # 2. Exactly at threshold (e.g. 30.0 C)
                if (base_param, val_exact) not in self.seen_boundaries:
                    self.seen_boundaries.add((base_param, val_exact))
                    tc_exact = TestCase(
                        id=self._next_id("BOUND"),
                        name=f"Threshold Boundary Exact: {base_param} at {val_exact} {unit}",
                        category=TestCategory.BOUNDARY,
                        description=f"Verify strict boundary condition handling exactly at threshold ({thresh} {unit}).",
                        priority=TestPriority.CRITICAL,
                        preconditions=["System operational in normal monitoring state"],
                        inputs={base_param: val_exact, "threshold": thresh, "unit": unit},
                        actions=[
                            f"Inject {base_param} input exactly at threshold ({val_exact} {unit})",
                            "Execute control loop evaluation",
                        ],
                        expected_outputs=self._get_normal_outputs(),
                        expected_behavior=(
                            bc.edge_case_notes or
                            bc.behavior_at_or_below or
                            f"At exact boundary ({val_exact} {unit}), condition <= {thresh} holds; remains inactive."
                        ),
                        failure_conditions=[f"Premature boundary trip or oscillation at exactly {val_exact} {unit}"],
                        hardware_requirements=self._build_hardware_requirements(),
                        expected_serial_log="Normal Range",
                        metadata={"boundary_type": "threshold", "position": "exact", "threshold": thresh, "value": val_exact},
                    )
                    self._add_test_case(suite, tc_exact)

                # 3. Immediately above threshold (e.g. 31.0 C)
                if (base_param, val_above) not in self.seen_boundaries:
                    self.seen_boundaries.add((base_param, val_above))
                    tc_above = TestCase(
                        id=self._next_id("BOUND"),
                        name=f"Threshold Boundary Above: {base_param} at {val_above} {unit}",
                        category=TestCategory.BOUNDARY,
                        description=f"Verify activation immediately above decision threshold ({thresh} {unit}).",
                        priority=TestPriority.HIGH,
                        preconditions=["System operational in normal monitoring state"],
                        inputs={base_param: val_above, "threshold": thresh, "unit": unit},
                        actions=[
                            f"Inject {base_param} input of {val_above} {unit} (1 {unit} above {thresh} {unit} threshold)",
                            "Execute control loop evaluation",
                        ],
                        expected_outputs=self._get_active_outputs(),
                        expected_behavior=bc.behavior_above or f"Threshold {thresh} exceeded; system actuates active state.",
                        failure_conditions=[f"Actuator failed to engage when threshold exceeded at {val_above} {unit}"],
                        hardware_requirements=self._build_hardware_requirements(),
                        expected_serial_log="Threshold Exceeded",
                        metadata={"boundary_type": "threshold", "position": "above", "threshold": thresh, "value": val_above},
                    )
                    self._add_test_case(suite, tc_above)

        # B. Documented sensor limits (-20 C, 120 C, below -20 C, above 120 C)
        for bc in self.analysis.boundary_conditions:
            param = bc.parameter
            base_param = self._normalize_param_name(param)
            unit = bc.unit or ""
            delta = 1.0

            # Lower limit (-20 C and below)
            if bc.min_limit is not None:
                min_lim = float(bc.min_limit)
                val_at_min = min_lim
                val_below_min = round(min_lim - delta, 1)

                if (base_param, val_at_min) not in self.seen_boundaries:
                    self.seen_boundaries.add((base_param, val_at_min))
                    tc_at_min = TestCase(
                        id=self._next_id("BOUND"),
                        name=f"Sensor Boundary Min Limit: {base_param} at {val_at_min} {unit}",
                        category=TestCategory.BOUNDARY,
                        description=f"Verify valid operation at lowest documented sensor boundary ({val_at_min} {unit}).",
                        priority=TestPriority.HIGH,
                        preconditions=["System initialized and sensor online"],
                        inputs={base_param: val_at_min, "limit": min_lim, "unit": unit},
                        actions=[
                            f"Inject sensor reading at minimum operational limit ({val_at_min} {unit})",
                            "Execute sensor validation routines",
                        ],
                        expected_outputs=self._get_normal_outputs(),
                        expected_behavior=f"Valid sensor reading at boundary {val_at_min} {unit}; system processes reading without error.",
                        failure_conditions=[f"False sensor fault reported at valid minimum reading {val_at_min} {unit}"],
                        hardware_requirements=self._build_hardware_requirements(),
                        metadata={"boundary_type": "sensor_limit", "position": "min_limit", "limit_value": min_lim},
                    )
                    self._add_test_case(suite, tc_at_min)

                if (base_param, val_below_min) not in self.seen_boundaries:
                    self.seen_boundaries.add((base_param, val_below_min))
                    tc_below_min = TestCase(
                        id=self._next_id("BOUND"),
                        name=f"Sensor Boundary Below Min Limit: {base_param} at {val_below_min} {unit}",
                        category=TestCategory.BOUNDARY,
                        description=f"Verify detection and handling of reading violating minimum sensor boundary ({val_below_min} {unit}).",
                        priority=TestPriority.CRITICAL,
                        preconditions=["System operational"],
                        inputs={base_param: val_below_min, "limit": min_lim, "unit": unit},
                        actions=[
                            f"Inject sensor reading violating lower boundary ({val_below_min} {unit} < {min_lim} {unit})",
                            "Execute boundary checking routine",
                        ],
                        expected_outputs=self._get_safe_outputs(),
                        expected_behavior=f"Reading below {min_lim} {unit} is recognized as out-of-range; triggers fault mitigation.",
                        failure_conditions=[f"System accepted out-of-range reading below {min_lim} {unit} as valid"],
                        hardware_requirements=self._build_hardware_requirements(),
                        expected_serial_log="ERROR",
                        metadata={"boundary_type": "sensor_limit", "position": "below_min", "limit_value": min_lim, "value": val_below_min},
                    )
                    self._add_test_case(suite, tc_below_min)

            # Upper limit (120 C and above)
            if bc.max_limit is not None:
                max_lim = float(bc.max_limit)
                val_at_max = max_lim
                val_above_max = round(max_lim + delta, 1)

                if (base_param, val_at_max) not in self.seen_boundaries:
                    self.seen_boundaries.add((base_param, val_at_max))
                    tc_at_max = TestCase(
                        id=self._next_id("BOUND"),
                        name=f"Sensor Boundary Max Limit: {base_param} at {val_at_max} {unit}",
                        category=TestCategory.BOUNDARY,
                        description=f"Verify operation at highest documented sensor boundary ({val_at_max} {unit}).",
                        priority=TestPriority.HIGH,
                        preconditions=["System initialized and sensor online"],
                        inputs={base_param: val_at_max, "limit": max_lim, "unit": unit},
                        actions=[
                            f"Inject sensor reading at maximum operational limit ({val_at_max} {unit})",
                            "Execute sensor processing routine",
                        ],
                        expected_outputs=self._get_active_outputs(),
                        expected_behavior=f"Valid sensor reading at maximum limit {val_at_max} {unit}; processed without fault.",
                        failure_conditions=[f"False sensor fault reported at valid maximum reading {val_at_max} {unit}"],
                        hardware_requirements=self._build_hardware_requirements(),
                        metadata={"boundary_type": "sensor_limit", "position": "max_limit", "limit_value": max_lim},
                    )
                    self._add_test_case(suite, tc_at_max)

                if (base_param, val_above_max) not in self.seen_boundaries:
                    self.seen_boundaries.add((base_param, val_above_max))
                    tc_above_max = TestCase(
                        id=self._next_id("BOUND"),
                        name=f"Sensor Boundary Above Max Limit: {base_param} at {val_above_max} {unit}",
                        category=TestCategory.BOUNDARY,
                        description=f"Verify detection and handling of reading violating maximum sensor boundary ({val_above_max} {unit}).",
                        priority=TestPriority.CRITICAL,
                        preconditions=["System operational"],
                        inputs={base_param: val_above_max, "limit": max_lim, "unit": unit},
                        actions=[
                            f"Inject sensor reading violating upper boundary ({val_above_max} {unit} > {max_lim} {unit})",
                            "Execute boundary checking routine",
                        ],
                        expected_outputs=self._get_safe_outputs(),
                        expected_behavior=f"Reading above {max_lim} {unit} is recognized as out-of-range; triggers fault mitigation.",
                        failure_conditions=[f"System accepted out-of-range reading above {max_lim} {unit} as valid"],
                        hardware_requirements=self._build_hardware_requirements(),
                        expected_serial_log="ERROR",
                        metadata={"boundary_type": "sensor_limit", "position": "above_max", "limit_value": max_lim, "value": val_above_max},
                    )
                    self._add_test_case(suite, tc_above_max)

    # =========================================================================
    # 3. ABNORMAL TESTS
    # =========================================================================
    def _generate_abnormal_tests(self, suite: TestSuite) -> None:
        for sensor in self.analysis.sensors:
            param = sensor.sensor_type
            unit = sensor.unit or ""

            # Extreme negative value
            tc_neg = TestCase(
                id=self._next_id("ABNORM"),
                name=f"Abnormal Extreme Negative Input: {param} at -999.0 {unit}",
                category=TestCategory.ABNORMAL,
                description=f"Stress-test input sanitizer against severe negative out-of-range {param} reading.",
                priority=TestPriority.MEDIUM,
                preconditions=["System running"],
                inputs={param: -999.0, "unit": unit},
                actions=[
                    f"Inject extreme negative {param} of -999.0 {unit}",
                    "Verify firmware error trap and sanitization",
                ],
                expected_outputs=self._get_safe_outputs(),
                expected_behavior="System safely rejects extreme negative input and asserts fail-safe state.",
                failure_conditions=["System crashes, overflows, or enters undefined state on extreme negative input"],
                hardware_requirements=self._build_hardware_requirements(),
                expected_serial_log="ERROR",
                metadata={"test_type": "extreme_negative", "value": -999.0},
            )
            self._add_test_case(suite, tc_neg)

            # Extreme positive value
            tc_pos = TestCase(
                id=self._next_id("ABNORM"),
                name=f"Abnormal Extreme Positive Input: {param} at +999.0 {unit}",
                category=TestCategory.ABNORMAL,
                description=f"Stress-test input sanitizer against severe positive out-of-range {param} reading.",
                priority=TestPriority.MEDIUM,
                preconditions=["System running"],
                inputs={param: 999.0, "unit": unit},
                actions=[
                    f"Inject extreme positive {param} of 999.0 {unit}",
                    "Verify firmware error trap and sanitization",
                ],
                expected_outputs=self._get_safe_outputs(),
                expected_behavior="System safely rejects extreme positive input and asserts fail-safe state.",
                failure_conditions=["System crashes, overflows, or enters undefined state on extreme positive input"],
                hardware_requirements=self._build_hardware_requirements(),
                expected_serial_log="ERROR",
                metadata={"test_type": "extreme_positive", "value": 999.0},
            )
            self._add_test_case(suite, tc_pos)

    # =========================================================================
    # 4. SENSOR FAILURE TESTS
    # =========================================================================
    def _generate_sensor_failure_tests(self, suite: TestSuite) -> None:
        sensor_fault_rules = [
            r for r in self.analysis.error_handling
            if "sensor" in r.fault_type.lower() or "sensor" in r.error_id.lower() or "reading" in r.trigger_condition.lower()
        ]

        has_sensor = len(self.analysis.sensors) > 0
        if sensor_fault_rules or has_sensor:
            rule = sensor_fault_rules[0] if sensor_fault_rules else None
            fault_state = next((s for s in self.analysis.states if s.is_error_state), None)
            fault_state_name = fault_state.name if fault_state else "FAULT_STATE"

            # Derive fault temperature from boundary conditions
            bc = next((b for b in self.analysis.boundary_conditions if b.min_limit is not None), None)
            min_limit = float(bc.min_limit) if bc else -20.0
            fault_reading = round(min_limit - 79.0, 1)

            # Derive sensor parameter name from sensors
            sensor_param = self.analysis.sensors[0].sensor_type if self.analysis.sensors else "input"

            # Derive expected serial log from testable_behaviors or error_handling
            fault_serial = next(
                (tb.expected_serial_log for tb in self.analysis.testable_behaviors
                 if tb.expected_serial_log and ("fault" in tb.category.lower() or "disconnect" in tb.name.lower())),
                None,
            )
            if not fault_serial and rule:
                fault_serial = f"ERROR: {rule.error_id}"
            if not fault_serial:
                fault_serial = "ERROR"

            tc_disconnect = TestCase(
                id=self._next_id("FAIL"),
                name="Sensor Disconnection and Hardware Fault Mitigation",
                category=TestCategory.SENSOR_FAILURE,
                description="Simulate physical sensor disconnection / open circuit and verify fail-safe shutdown.",
                priority=TestPriority.CRITICAL,
                preconditions=["System active with cooling or normal monitoring engaged"],
                inputs={sensor_param: fault_reading, "sensor_connected": False, "signal_fault": "OPEN_CIRCUIT"},
                actions=[
                    f"Disconnect physical sensor signal wire (open circuit: {fault_reading} reading)",
                    "Invoke sensor processing routine",
                    "Verify immediate transition to safe fault state",
                ],
                expected_outputs=self._get_safe_outputs(),
                expected_behavior=(
                    f"System detects sensor fault, transitions to '{fault_state_name}', deactivates actuators "
                    "to prevent unmonitored operation, and emits serial alert."
                ),
                failure_conditions=[
                    "Actuator remains active during sensor disconnection",
                    f"System fails to transition to '{fault_state_name}'",
                    "Error alert not logged over serial",
                ],
                hardware_requirements=self._build_hardware_requirements(),
                expected_serial_log=fault_serial,
                metadata={"fault_type": rule.fault_type if rule else "sensor_disconnection"},
            )
            self._add_test_case(suite, tc_disconnect)

    # =========================================================================
    # 5. STATE TRANSITION TESTS
    # =========================================================================
    def _generate_state_transition_tests(self, suite: TestSuite) -> None:
        # Pre-compute reference values from boundary conditions
        bc = next((b for b in self.analysis.boundary_conditions if b.threshold is not None), None)
        if bc and bc.threshold is not None:
            thresh = float(bc.threshold)
            min_lim = float(bc.min_limit) if bc.min_limit is not None else -20.0
            active_val = round(thresh + 2.5, 1)
            normal_val = round(thresh - 2.0, 1)
            idle_val = round(thresh - 5.0, 1)
            fault_val = round(min_lim - 79.0, 1)
        else:
            thresh = None
            active_val = 50.0
            normal_val = 20.0
            idle_val = 15.0
            fault_val = -99.0

        for trans in self.analysis.state_transitions:
            dest_state = next((s for s in self.analysis.states if s.name == trans.to_state), None)
            expected_outs = dest_state.expected_outputs if dest_state and dest_state.expected_outputs else self._get_safe_outputs() if (dest_state and dest_state.is_error_state) else self._get_normal_outputs()

            # Determine input stimulus from trigger and destination state — derived from boundary_conditions
            stimulus_input: Dict[str, Any] = {"trigger": trans.trigger}

            # Identify the primary sensor parameter
            sensor_param = self.analysis.sensors[0].sensor_type if self.analysis.sensors else "input"

            if "fault" in trans.trigger.lower() or "disconnection" in trans.trigger.lower() or (dest_state and dest_state.is_error_state):
                stimulus_input[sensor_param] = fault_val
            elif "active" in trans.to_state.lower() or "exceed" in trans.trigger.lower():
                stimulus_input[sensor_param] = active_val
            elif "normal" in trans.to_state.lower() or "cool" in trans.to_state.lower() or "idle" in trans.to_state.lower():
                stimulus_input[sensor_param] = normal_val
            else:
                stimulus_input[sensor_param] = idle_val


            tc_trans = TestCase(
                id=self._next_id("STATE"),
                name=f"State Transition: {trans.from_state} -> {trans.to_state}",
                category=TestCategory.STATE_TRANSITION,
                description=f"Validate state transition from '{trans.from_state}' to '{trans.to_state}' upon '{trans.trigger}'.",
                priority=TestPriority.HIGH,
                preconditions=[f"System established in source state '{trans.from_state}'"],
                inputs=stimulus_input,
                actions=[
                    f"Configure system to state '{trans.from_state}'",
                    f"Apply transition trigger condition: {trans.trigger}",
                    "Inspect state variable and hardware pin outputs",
                ],
                expected_outputs=expected_outs,
                expected_behavior=(
                    f"System successfully transitions from '{trans.from_state}' to '{trans.to_state}'. "
                    f"Action executed: {trans.action_on_transition or 'None'}."
                ),
                failure_conditions=[
                    f"System failed to transition to '{trans.to_state}'",
                    "System transitioned to incorrect state or locked up",
                    "Output pins do not match destination state specifications",
                ],
                hardware_requirements=self._build_hardware_requirements(),
                metadata={
                    "from_state": trans.from_state,
                    "to_state": trans.to_state,
                    "trigger": trans.trigger,
                    "guard": trans.guard_condition,
                },
            )
            self._add_test_case(suite, tc_trans)

    # =========================================================================
    # 6. COMMUNICATION FAILURE TESTS
    # =========================================================================
    def _generate_communication_failure_tests(self, suite: TestSuite) -> None:
        """
        Only generate communication failure tests if the firmware analysis documents
        explicit communication failure behavior, communication timeout error handling, or protocol faults.
        If communication interface is purely telemetry/logging with no comm error handling, generate none.
        """
        comm_fault_rules = [
            r for r in self.analysis.error_handling
            if any(k in r.fault_type.lower() for k in ["comm", "communication", "uart_error", "i2c_error", "spi_error", "bus_fault"])
            or any(k in r.trigger_condition.lower() for k in ["comm_timeout", "packet_loss", "framing_error", "crc_error", "bus_off"])
        ]

        comm_transitions = [
            t for t in self.analysis.state_transitions
            if any(k in t.trigger.lower() or k in (t.guard_condition or "").lower() for k in ["comm_loss", "comm_timeout", "bus_error", "packet_timeout"])
        ]

        # Only generate if explicit communication failure behavior exists
        if comm_fault_rules or comm_transitions:
            for iface in self.analysis.communication_interfaces:
                tc_comm = TestCase(
                    id=self._next_id("COMM"),
                    name=f"Communication Failure: {iface.interface_type} Timeout and Bus Error",
                    category=TestCategory.COMMUNICATION_FAILURE,
                    description=f"Validate firmware fault handling upon communication failure on {iface.interface_type}.",
                    priority=TestPriority.HIGH,
                    preconditions=[f"Interface {iface.interface_type} active and initialized"],
                    inputs={"interface": iface.interface_type, "bus_status": "DISCONNECTED", "timeout_ms": 2000},
                    actions=[
                        f"Interrupt communication signal lines on {iface.interface_type}",
                        "Wait for communication timeout to expire",
                        "Verify fault handling and recovery state",
                    ],
                    expected_outputs=self._get_safe_outputs(),
                    expected_behavior=f"System detects communication failure on {iface.interface_type} and executes configured mitigation.",
                    failure_conditions=[f"System hangs or fails to detect communication timeout on {iface.interface_type}"],
                    hardware_requirements=self._build_hardware_requirements(),
                    metadata={"interface": iface.interface_type},
                )
                self._add_test_case(suite, tc_comm)

    # =========================================================================
    # 7. UNEXPECTED INPUT TESTS
    # =========================================================================
    def _generate_unexpected_input_tests(self, suite: TestSuite) -> None:
        bc = next((b for b in self.analysis.boundary_conditions if b.threshold is not None), None)
        if bc and bc.threshold is not None:
            thresh = bc.threshold
            param = self._normalize_param_name(bc.parameter)
            unit = bc.unit or ""

            tc_jitter = TestCase(
                id=self._next_id("UNEXP"),
                name=f"Unexpected Input: High-Frequency Jitter Around Threshold ({thresh} {unit})",
                category=TestCategory.UNEXPECTED_INPUT,
                description=f"Inject rapid alternating readings ({thresh - 0.2:.1f} {unit} and {thresh + 0.2:.1f} {unit}) to test debouncing/hysteresis.",
                priority=TestPriority.MEDIUM,
                preconditions=["System in normal operational loop"],
                inputs={"param": param, "signal": "JITTER", "frequency_hz": 50, "amplitude": 0.4},
                actions=[
                    f"Inject fluctuating input rapidly crossing {thresh} {unit} threshold at 50Hz",
                    "Monitor output relay line for chatter or race conditions",
                ],
                expected_outputs=self._get_normal_outputs(),
                expected_behavior="System remains stable without relay chatter or undefined oscillation.",
                failure_conditions=["Relay chatters uncontrollably or controller enters race condition"],
                hardware_requirements=self._build_hardware_requirements(),
                metadata={"test_type": "jitter_hysteresis", "threshold": thresh},
            )
            self._add_test_case(suite, tc_jitter)

    # =========================================================================
    # 8. COMBINATION TESTS
    # =========================================================================
    def _generate_combination_tests(self, suite: TestSuite) -> None:
        # High-value combination 1: Cold Boot at High Temperature
        bc = next((b for b in self.analysis.boundary_conditions if b.threshold is not None), None)
        if bc and bc.threshold is not None:
            high_temp = round(bc.threshold + 5.0, 1)
            param = self._normalize_param_name(bc.parameter)
            tc_boot_high = TestCase(
                id=self._next_id("COMB"),
                name=f"Combination: Cold Boot with Pre-Existing Elevated {param} ({high_temp} {bc.unit})",
                category=TestCategory.COMBINATION,
                description=(
                    f"Evaluate initial boot behavior when ambient {param} is already exceeding {bc.threshold} {bc.unit}. "
                    "Verifies system does not stay stuck in idle if started in hot environment."
                ),
                priority=TestPriority.HIGH,
                preconditions=["Hardware in powered-down cold state", f"Ambient {param} established at {high_temp} {bc.unit}"],
                inputs={"power": "ON", param: high_temp},
                actions=[
                    f"Preset {param} stimulus to {high_temp} {bc.unit}",
                    "Apply power / release reset",
                    "Observe state transition from boot to active cooling",
                ],
                expected_outputs=self._get_active_outputs(),
                expected_behavior=f"System boots, immediately detects {param} > {bc.threshold}, and transitions directly to active cooling.",
                failure_conditions=["System remains in idle state despite elevated startup temperature"],
                hardware_requirements=self._build_hardware_requirements(),
                expected_serial_log="Threshold Exceeded",
                metadata={"combination_type": "boot_at_high_threshold"},
            )
            self._add_test_case(suite, tc_boot_high)

        # High-value combination 2: Sensor Disconnect During Active Actuation
        if self.analysis.actuators and any("sensor" in r.fault_type.lower() for r in self.analysis.error_handling):
            # Derive values from boundary conditions
            bc_combo = next((b for b in self.analysis.boundary_conditions if b.threshold is not None), None)
            active_temp = round(bc_combo.threshold + 5.0, 1) if bc_combo and bc_combo.threshold else 35.0
            bc_min = next((b for b in self.analysis.boundary_conditions if b.min_limit is not None), None)
            combo_fault_val = round(float(bc_min.min_limit) - 79.0, 1) if bc_min and bc_min.min_limit is not None else -99.0
            sensor_p = self.analysis.sensors[0].sensor_type if self.analysis.sensors else "input"

            # Derive fault serial from testable_behaviors
            combo_fault_serial = next(
                (tb.expected_serial_log for tb in self.analysis.testable_behaviors
                 if tb.expected_serial_log and ("fault" in tb.category.lower() or "disconnect" in tb.name.lower())),
                "ERROR",
            )

            tc_disconnect_active = TestCase(
                id=self._next_id("COMB"),
                name="Combination: Sudden Sensor Disconnection During Active Actuator Run",
                category=TestCategory.COMBINATION,
                description="Verify fail-safe shutdown occurs immediately when sensor disconnects while actuator is actively engaged.",
                priority=TestPriority.CRITICAL,
                preconditions=[f"System running in active state with actuator energized (e.g. at {active_temp})"],
                inputs={f"initial_{sensor_p}": active_temp, "fault_injection": "SENSOR_DISCONNECTED", "fault_reading": combo_fault_val},
                actions=[
                    f"Establish active state ({sensor_p} = {active_temp}, actuator = ON)",
                    f"Suddenly disconnect sensor wire ({combo_fault_val} reading)",
                    "Verify actuator is de-energized within one execution cycle",
                ],
                expected_outputs=self._get_safe_outputs(),
                expected_behavior="Actuator is immediately de-energized and system transitions to fault state without lingering.",
                failure_conditions=["Actuator remains energized after sensor fault injection"],
                hardware_requirements=self._build_hardware_requirements(),
                expected_serial_log=combo_fault_serial,
                metadata={"combination_type": "sensor_fault_under_load"},
            )
            self._add_test_case(suite, tc_disconnect_active)


def generate_tests(analysis: FirmwareAnalysis) -> TestSuite:
    """Entrypoint function to deterministically generate a TestSuite from FirmwareAnalysis."""
    generator = DeterministicTestGenerator(analysis)
    return generator.generate()
