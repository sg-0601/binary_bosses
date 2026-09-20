from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CompilationRequest(BaseModel):
    source_file: str = Field(..., description="Path to C/C++ source file")
    output_binary: Optional[str] = Field(None, description="Path for output binary")
    compiler_flags: Optional[List[str]] = Field(default_factory=list, description="Extra compiler flags")


class CompilationResult(BaseModel):
    success: bool
    output_file: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0


class SimulationRequest(BaseModel):
    project_dir: str = Field(..., description="Directory containing wokwi.toml / diagram.json")
    timeout_ms: int = Field(default=8000, description="Simulation timeout in milliseconds")
    expect_text: Optional[str] = Field(None, description="Expected text to look for in serial output")
    fail_text: Optional[str] = Field(None, description="Text that triggers immediate test failure")
    scenario_file: Optional[str] = Field(None, description="Optional path to scenario.yaml")
    use_mock_fallback: bool = Field(default=False, description="Fallback to mock simulator if token missing")
    compiled_binary: Optional[str] = Field(None, description="Optional path to host-compiled binary")


class SimulationResult(BaseModel):
    success: bool
    exit_code: int
    captured_serial: str = ""
    matched_expected: Optional[bool] = None
    matched_failed: Optional[bool] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    log_file_path: Optional[str] = None
    is_real_execution: bool = True
    mock_used: bool = False


class FirmwareAnalysisRequest(BaseModel):
    source_code: Optional[str] = Field(None, description="C/C++ firmware source code to analyze")
    source_file: Optional[str] = Field(None, description="Optional path to C/C++ source file on disk")
    target_hardware: str = Field(default="esp32-devkit-c", description="Target hardware board or architecture")


class FailureAnalysis(BaseModel):
    status: str
    bug_detected: bool
    root_cause: str
    affected_lines: Optional[str] = None
    suggested_fix: Optional[str] = None


class TestRunRequest(BaseModel):
    test_name: str = Field(default="Automated ESP32 Firmware Test")
    project_dir: str = Field(..., description="Path to Wokwi project directory")
    source_file: Optional[str] = Field(None, description="Path to C/C++ firmware source file")
    expect_text: Optional[str] = Field(None, description="Expected string in serial logs")
    timeout_ms: int = Field(default=8000, description="Timeout in ms")
    use_mock_fallback: bool = Field(default=False, description="Whether mock fallback is allowed")


class TestRunResult(BaseModel):
    test_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    test_name: str
    status: str  # PASSED, FAILED, TIMEOUT, ERROR
    serial_output: str = ""
    duration_ms: float = 0.0
    is_real_execution: bool = True
    mock_used: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class HealthStatus(BaseModel):
    status: str
    wokwi_cli_installed: bool
    wokwi_cli_path: str
    wokwi_token_configured: bool
    gcc_installed: bool
    gcc_path: str
    python_version: str
    arduino_cli_installed: bool = False
    arduino_cli_path: str = ""
    esp32_core_installed: bool = False
    gemini_configured: bool = False
    gemini_model: str = ""
    firmware_execution_mode: str = "demo"
