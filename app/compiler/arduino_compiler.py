"""
Arduino CLI Embedded Compiler Service
Cross-compiles embedded C/C++ firmware sketches into .bin and .elf binaries for ESP32 target.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional, List
from app.models.schemas import CompilationRequest, CompilationResult
from app.utils.config import settings


class ArduinoCompiler:
    """Manages embedded cross-compilation for MCU targets using Arduino CLI."""

    def __init__(self, cli_path: Optional[str] = None, fqbn: Optional[str] = None):
        self.cli_path = cli_path or settings.get_arduino_cli_executable()
        self.fqbn = fqbn or settings.ESP32_FQBN

    def check_installed(self) -> bool:
        """Verify arduino-cli is accessible and runnable."""
        try:
            res = subprocess.run([self.cli_path, "version"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False

    def is_esp32_installed(self) -> bool:
        """Verify esp32 platform core is installed."""
        try:
            res = subprocess.run([self.cli_path, "core", "list"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0 and "esp32" in res.stdout
        except Exception:
            return False

    def compile(
        self,
        sketch_path: str,
        output_dir: Optional[str] = None,
        fqbn: Optional[str] = None
    ) -> CompilationResult:
        """
        Cross-compile sketch using arduino-cli.
        Produces .bin and .elf files in output_dir.
        """
        src = Path(sketch_path)
        if not src.is_absolute():
            src = (settings.PROJECT_ROOT / src).resolve()

        if not src.exists():
            return CompilationResult(
                success=False,
                stdout="",
                stderr=f"Sketch path not found: {src}",
                duration_ms=0.0
            )

        target_fqbn = fqbn or self.fqbn
        out_dir = Path(output_dir) if output_dir else src.parent
        if not out_dir.is_absolute():
            out_dir = (settings.PROJECT_ROOT / out_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.cli_path,
            "compile",
            "--fqbn", target_fqbn,
            "--output-dir", str(out_dir),
            str(src)
        ]

        start = time.perf_counter()
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            duration_ms = (time.perf_counter() - start) * 1000.0

            # Look for generated .bin or .elf
            output_file = None
            if process.returncode == 0:
                bin_files = list(out_dir.glob("*.bin"))
                if bin_files:
                    output_file = str(bin_files[0])

            return CompilationResult(
                success=(process.returncode == 0),
                output_file=output_file,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_ms=round(duration_ms, 2)
            )
        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                stdout="",
                stderr="Arduino CLI compilation timed out after 120 seconds",
                duration_ms=120000.0
            )
        except Exception as exc:
            return CompilationResult(
                success=False,
                stdout="",
                stderr=str(exc),
                duration_ms=0.0
            )


arduino_compiler = ArduinoCompiler()
