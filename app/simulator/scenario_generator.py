"""
Wokwi Scenario and Per-Test Project Generator
Creates an isolated Wokwi project directory and scenario.yaml for each TestCase.
"""

import shutil
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.test_case import TestCase
from app.utils.config import settings


class GeneratedScenario(BaseModel):
    """Result of generating an isolated Wokwi test project and scenario from a TestCase."""
    __test__ = False

    project_dir: str = Field(..., description="Absolute path to isolated test project directory")
    scenario_path: str = Field(..., description="Absolute path to generated scenario.yaml")
    test_id: str = Field(..., description="ID of the test case")
    test_name: str = Field("", description="Name of the test case")
    expected_serial_patterns: List[str] = Field(default_factory=list,
        description="Serial text patterns the scenario expects to see")
    scenario_content: Dict[str, Any] = Field(default_factory=dict,
        description="The scenario YAML content as a dict")


class ScenarioGenerator:
    """
    Creates an isolated per-test Wokwi project directory containing:
    - diagram.json (copied from base demo project)
    - wokwi.toml (referencing precompiled demo binaries)
    - fan_controller.ino.bin / fan_controller.ino.elf (copied for full isolation)
    - scenario.yaml (with wait-serial steps)
    """

    def __init__(self):
        self._demo_src_dir = settings.PROJECT_ROOT / "wokwi" / "projects" / "fan_controller"

    def generate(
        self,
        test_case: TestCase,
        run_dir: Path,
        timeout_ms: int = 5000,
    ) -> GeneratedScenario:
        """
        Build an isolated per-test Wokwi project directory and generate scenario.yaml.

        Args:
            test_case: The test case to generate a scenario for.
            run_dir: Parent directory for this test run.
            timeout_ms: Wokwi scenario timeout.

        Returns:
            GeneratedScenario with project_dir, scenario_path, and metadata.
        """
        test_project_dir = run_dir / test_case.id
        test_project_dir.mkdir(parents=True, exist_ok=True)

        # 1. Copy diagram.json
        diagram_src = self._demo_src_dir / "diagram.json"
        if diagram_src.exists():
            shutil.copy(diagram_src, test_project_dir / "diagram.json")

        # 2. Copy firmware binaries into isolated test directory
        for bin_name in ["fan_controller.ino.bin", "fan_controller.ino.elf"]:
            src_bin = self._demo_src_dir / bin_name
            if src_bin.exists():
                shutil.copy(src_bin, test_project_dir / bin_name)

        # 3. Create isolated wokwi.toml
        toml_content = (
            "[wokwi]\n"
            "version = 1\n"
            "elf = \"fan_controller.ino.elf\"\n"
            "firmware = \"fan_controller.ino.bin\"\n"
        )
        (test_project_dir / "wokwi.toml").write_text(toml_content, encoding="utf-8")

        # 4. Build scenario steps
        steps = []
        expected_patterns = []

        if test_case.expected_serial_log:
            pattern = test_case.expected_serial_log.strip()
            # If multi-line, take the most distinctive line
            first_line = pattern.splitlines()[0].strip()
            if len(first_line) > 80:
                first_line = first_line[:80]
            steps.append({"wait-serial": first_line})
            expected_patterns.append(first_line)

        # Default fallback if no serial pattern is expected
        if not steps:
            steps.append({"wait-serial": "[SYSTEM_BOOT]"})
            expected_patterns.append("[SYSTEM_BOOT]")

        scenario_content = {
            "name": f"{test_case.id} - {test_case.name}",
            "version": 1,
            "steps": steps,
        }

        scenario_path = test_project_dir / "scenario.yaml"
        with open(scenario_path, "w", encoding="utf-8") as f:
            yaml.dump(scenario_content, f, sort_keys=False, default_flow_style=False)

        return GeneratedScenario(
            project_dir=str(test_project_dir),
            scenario_path=str(scenario_path),
            test_id=test_case.id,
            test_name=test_case.name,
            expected_serial_patterns=expected_patterns,
            scenario_content=scenario_content,
        )


scenario_generator = ScenarioGenerator()
