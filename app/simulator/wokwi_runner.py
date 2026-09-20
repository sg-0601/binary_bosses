import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional
from app.models.schemas import SimulationRequest, SimulationResult
from app.utils.config import settings


class WokwiRunner:
    """Manages headless execution of embedded firmware inside Wokwi CLI."""

    def __init__(self, cli_path: Optional[str] = None):
        self.cli_path = cli_path or settings.get_wokwi_executable()

    def is_installed(self) -> bool:
        """Check if wokwi-cli executable exists and responds."""
        try:
            res = subprocess.run([self.cli_path, "--version"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False

    def get_version(self) -> str:
        try:
            res = subprocess.run([self.cli_path, "--version"], capture_output=True, text=True, timeout=5)
            return res.stdout.strip()
        except Exception as e:
            return f"Unavailable ({e})"

    def has_token(self) -> bool:
        """Check if WOKWI_CLI_TOKEN is set in config or environment."""
        token = settings.WOKWI_CLI_TOKEN or os.environ.get("WOKWI_CLI_TOKEN", "")
        return bool(token.strip())

    def run_simulation(self, request: SimulationRequest) -> SimulationResult:
        """Execute a firmware simulation via Wokwi CLI and capture serial output."""
        project_path = Path(request.project_dir)
        if not project_path.is_absolute():
            project_path = (settings.PROJECT_ROOT / project_path).resolve()

        if not project_path.exists():
            return SimulationResult(
                success=False,
                exit_code=1,
                is_real_execution=False,
                mock_used=False,
                stderr=f"Project directory not found: {project_path}"
            )

        # Ensure unique log file path in test_results directory
        results_dir = settings.get_results_path()
        run_id = str(uuid.uuid4())[:8]
        log_file = results_dir / f"serial_{run_id}.log"

        # Check token requirement
        token = settings.WOKWI_CLI_TOKEN or os.environ.get("WOKWI_CLI_TOKEN", "")

        # Strict validation: Missing token must fail clearly if mock fallback is not explicitly requested
        if not token.strip():
            if request.use_mock_fallback:
                return self._run_mock_simulation(request, log_file)
            return SimulationResult(
                success=False,
                exit_code=1,
                is_real_execution=False,
                mock_used=False,
                stderr="AUTHENTICATION ERROR: WOKWI_CLI_TOKEN is not configured in .env or system environment. "
                       "Real Wokwi CLI execution requires a valid token from https://wokwi.com/dashboard/ci."
            )

        # Check if firmware binary specified in wokwi.toml exists on disk
        firmware_missing = False
        toml_path = project_path / "wokwi.toml"
        if toml_path.exists():
            try:
                for line in toml_path.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("firmware"):
                        fw_name = line.split("=")[1].strip().strip("'\"")
                        if not (project_path / fw_name).exists():
                            firmware_missing = True
                            break
            except Exception:
                pass

        if firmware_missing:
            if request.use_mock_fallback:
                return self._run_mock_simulation(request, log_file)
            return SimulationResult(
                success=False,
                exit_code=1,
                is_real_execution=False,
                mock_used=False,
                stderr=f"CONFIGURATION ERROR: Firmware binary specified in wokwi.toml does not exist in {project_path}."
            )

        # Build CLI command
        cmd = [
            self.cli_path,
            "--timeout", str(request.timeout_ms),
            "--serial-log-file", str(log_file),
        ]

        if request.expect_text:
            cmd.extend(["--expect-text", request.expect_text])

        if request.fail_text:
            cmd.extend(["--fail-text", request.fail_text])

        if request.scenario_file:
            scen_path = Path(request.scenario_file)
            if not scen_path.is_absolute():
                scen_path = (project_path / scen_path).resolve()
            if scen_path.exists():
                try:
                    rel_scen = scen_path.relative_to(project_path)
                    cmd.extend(["--scenario", str(rel_scen)])
                except ValueError:
                    cmd.extend(["--scenario", scen_path.name])

        cmd.append(str(project_path))

        env = os.environ.copy()
        env["WOKWI_CLI_TOKEN"] = token.strip()

        start = time.perf_counter()
        try:
            # Add safety margin to subprocess timeout
            proc_timeout = (request.timeout_ms / 1000.0) + 15.0
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=proc_timeout,
                env=env,
                cwd=str(settings.PROJECT_ROOT)
            )
            duration_ms = (time.perf_counter() - start) * 1000.0

            # Read captured serial output from log file if generated
            captured_serial = ""
            if log_file.exists():
                try:
                    captured_serial = log_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

            # If log file is empty, fallback to stdout inspection
            if not captured_serial and process.stdout:
                captured_serial = process.stdout

            matched_expected = None
            if request.expect_text:
                matched_expected = (request.expect_text in captured_serial)

            matched_failed = None
            if request.fail_text:
                matched_failed = (request.fail_text in captured_serial)

            success = (process.returncode == 0)
            if matched_expected is True and matched_failed is not True:
                success = True
            elif matched_expected is False:
                success = False
            if matched_failed is True:
                success = False

            return SimulationResult(
                success=success,
                exit_code=process.returncode,
                captured_serial=captured_serial,
                matched_expected=matched_expected,
                matched_failed=matched_failed,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_ms=round(duration_ms, 2),
                log_file_path=str(log_file) if log_file.exists() else None,
                is_real_execution=True,
                mock_used=False
            )

        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return SimulationResult(
                success=False,
                exit_code=42,  # Wokwi timeout exit code
                stderr="Simulation process timed out after allocated limit",
                duration_ms=round(duration_ms, 2),
                is_real_execution=True,
                mock_used=False
            )
        except Exception as e:
            return SimulationResult(
                success=False,
                exit_code=-1,
                is_real_execution=True,
                mock_used=False,
                stderr=f"Execution error: {str(e)}"
            )

    def _run_mock_simulation(self, request: SimulationRequest, log_file: Path) -> SimulationResult:
        """
        Mock simulation fallback — ONLY used when explicitly permitted for dev/unit testing.
        
        CRITICAL: Mock execution can NEVER produce PASS (success=True).
        Always returns success=False, mock_used=True.
        """
        mock_notice = (
            "[MOCK] This is a mock simulation — NOT real Wokwi execution.\n"
            "[MOCK] Results are NOT authoritative. Use real Wokwi CLI for valid testing.\n"
        )
        log_file.write_text(mock_notice, encoding="utf-8")

        return SimulationResult(
            success=False,
            exit_code=-1,
            captured_serial=mock_notice,
            matched_expected=None,
            matched_failed=None,
            stdout="MOCK: Mock simulation executed — result is NOT authoritative",
            stderr="MOCK execution does not produce valid PASS/FAIL results",
            duration_ms=1.0,
            log_file_path=str(log_file),
            is_real_execution=False,
            mock_used=True
        )


simulator = WokwiRunner()
