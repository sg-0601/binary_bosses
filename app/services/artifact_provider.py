"""
Execution Artifact Provider
Manages firmware execution artifacts for DEMO and future COMPILE modes.
"""

from pathlib import Path
from typing import Dict, Any
from app.utils.config import settings


class ExecutionArtifactProvider:
    """
    Provides execution artifacts (firmware binaries, project config) based on execution mode.
    
    DEMO mode: uses known-good precompiled ESP32 fan_controller artifact.
    COMPILE mode: future - would use freshly compiled firmware.
    """

    def __init__(self):
        self.mode = settings.FIRMWARE_EXECUTION_MODE
        self._demo_project_dir = settings.PROJECT_ROOT / "wokwi" / "projects" / "fan_controller"

    @property
    def demo_project_dir(self) -> Path:
        return self._demo_project_dir

    def get_project_dir(self) -> Path:
        """Return the Wokwi project directory containing wokwi.toml, diagram.json, and firmware."""
        if self.mode == "demo":
            return self._demo_project_dir
        raise NotImplementedError("Compile mode is not yet implemented. Use FIRMWARE_EXECUTION_MODE=demo.")

    def get_artifact_info(self) -> Dict[str, Any]:
        """Return metadata about the current execution artifact."""
        return {
            "mode": self.mode,
            "project_dir": str(self._demo_project_dir),
            "firmware_elf": "fan_controller.ino.elf",
            "firmware_bin": "fan_controller.ino.bin",
            "target_board": "ESP32 DevKitC",
            "notice": (
                "DEMO MODE: Firmware source is analyzed by AI. "
                "Simulation uses a known-good precompiled ESP32 demo artifact."
            ),
        }

    def validate(self) -> bool:
        """Check that all required demo artifacts exist on disk."""
        required = [
            self._demo_project_dir / "fan_controller.ino.elf",
            self._demo_project_dir / "fan_controller.ino.bin",
            self._demo_project_dir / "wokwi.toml",
            self._demo_project_dir / "diagram.json",
        ]
        return all(f.exists() for f in required)

    def get_missing_artifacts(self) -> list:
        """Return list of missing artifact file paths."""
        required = [
            self._demo_project_dir / "fan_controller.ino.elf",
            self._demo_project_dir / "fan_controller.ino.bin",
            self._demo_project_dir / "wokwi.toml",
            self._demo_project_dir / "diagram.json",
        ]
        return [str(f) for f in required if not f.exists()]


artifact_provider = ExecutionArtifactProvider()
