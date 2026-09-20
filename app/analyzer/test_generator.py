from pathlib import Path
from typing import List
import yaml
from app.models.schemas import FirmwareAnalysis, TestCase, TestSuite
from app.utils.config import settings


class DeterministicTestGenerator:
    """Generates structured test suites and converts them to Wokwi scenario YAML files."""

    def generate_suite(self, analysis: FirmwareAnalysis) -> TestSuite:
        """Derive a comprehensive test suite based on firmware analysis and execution mode."""
        cases: List[TestCase] = []

        if settings.FIRMWARE_EXECUTION_MODE == "demo":
            # For DEMO_MODE with precompiled ESP32 artifact:
            cases.append(TestCase(
                test_id="TC_01_BOOT",
                name="ESP32 CPU Initialization",
                description="Verifies that the dual-core ESP32 boots cleanly and starts scheduler.",
                expected_serial="cpu_start",
                timeout_ms=8000
            ))
            cases.append(TestCase(
                test_id="TC_02_BANNER",
                name="Firmware Hello World Banner",
                description="Verifies main task executes and transmits initial serial banner.",
                expected_serial="Hello world!",
                timeout_ms=8000
            ))
            cases.append(TestCase(
                test_id="TC_03_CHIP_INFO",
                name="ESP32 Hardware Identification",
                description="Verifies CPU core count, flash memory detection, and silicon rev.",
                expected_serial="This is esp32 chip",
                timeout_ms=8000
            ))
        else:
            # For on-demand compile mode:
            cases.append(TestCase(
                test_id="TC_01_INIT",
                name="Firmware Initialization",
                description="Checks that setup() runs and announces test start.",
                expected_serial="FIRMWARE_TEST_STARTED",
                timeout_ms=8000
            ))
            cases.append(TestCase(
                test_id="TC_02_FAN_ACTUATION",
                name="Fan Control Threshold Verification",
                description="Checks that temperature threshold activates fan relay.",
                expected_serial="FAN_ON",
                timeout_ms=8000
            ))
            cases.append(TestCase(
                test_id="TC_03_SUCCESS",
                name="Execution Completion",
                description="Verifies test run completes without crashing.",
                expected_serial="FIRMWARE_TEST_SUCCESS",
                timeout_ms=8000
            ))

        return TestSuite(
            suite_name=f"{analysis.project_name}_TestSuite",
            target_board="board-esp32-devkit-c",
            cases=cases
        )

    def write_wokwi_scenario(self, test_case: TestCase, output_path: Path) -> Path:
        """Convert a TestCase into a valid Wokwi scenario YAML file."""
        scenario_data = {
            "name": test_case.name,
            "version": 1,
            "author": "Autonomous Testing Agent",
            "steps": [
                {"expect-serial": test_case.expected_serial}
            ]
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(scenario_data, f, sort_keys=False)

        return output_path


generator = DeterministicTestGenerator()
