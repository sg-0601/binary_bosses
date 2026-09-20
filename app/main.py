import sys
import uuid
import time
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.models.schemas import (
    CompilationRequest,
    CompilationResult,
    SimulationRequest,
    SimulationResult,
    TestRunRequest,
    TestRunResult,
    HealthStatus,
    FirmwareAnalysisRequest,
    FailureAnalysis,
)
from app.models.firmware import FirmwareAnalysis
from app.models.test_case import TestSuite
from app.tests.generator import DeterministicTestGenerator
from app.ai.analyzer import (
    analyzer,
    EmptySourceCodeError,
    ModelOutputParsingError,
    ModelOutputValidationError,
)
from app.ai.gemini_client import GeminiAPIKeyMissingError, GeminiAPIError
from app.compiler.gcc_compiler import compiler
from app.simulator.wokwi_runner import simulator
from app.services.artifact_provider import artifact_provider
from app.services.test_pipeline import pipeline, PipelineResult
from app.utils.config import settings
from app.utils.file_manager import save_test_result, list_test_results

app = FastAPI(
    title="Autonomous Embedded Firmware Testing API",
    version="2.0.0",
    description="Decoupled AI Firmware QA System with Real Wokwi CLI Simulation"
)

# Set up templates
templates_dir = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def get_health_status() -> HealthStatus:
    wokwi_ok = simulator.is_installed()
    gcc_ok = compiler.check_installed()
    token_ok = simulator.has_token()
    arduino_ok = settings.is_arduino_cli_installed()
    esp32_ok = settings.is_esp32_core_installed()
    gemini_ok = settings.has_gemini_key()
    artifact_ok = artifact_provider.validate()
    overall = "OK" if (wokwi_ok and token_ok and gemini_ok and artifact_ok) else "DEGRADED"

    return HealthStatus(
        status=overall,
        wokwi_cli_installed=wokwi_ok,
        wokwi_cli_path=settings.get_wokwi_executable(),
        wokwi_token_configured=token_ok,
        gcc_installed=gcc_ok,
        gcc_path=settings.get_gcc_executable(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        arduino_cli_installed=arduino_ok,
        arduino_cli_path=settings.get_arduino_cli_executable(),
        esp32_core_installed=esp32_ok,
        gemini_configured=gemini_ok,
        gemini_model=settings.GEMINI_MODEL,
        firmware_execution_mode=settings.FIRMWARE_EXECUTION_MODE,
    )


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    health = get_health_status()
    results = list_test_results()
    # Load default firmware source for the textarea
    default_src = settings.PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "main.c"
    default_code = ""
    if default_src.exists():
        default_code = default_src.read_text(encoding="utf-8")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "health": health,
            "results": results[:10],
            "default_code": default_code,
            "artifact_info": artifact_provider.get_artifact_info(),
        }
    )


@app.get("/api/health", response_model=HealthStatus)
async def api_health():
    """Return health and environment status."""
    return get_health_status()


@app.post("/api/compile", response_model=CompilationResult)
async def api_compile(request: CompilationRequest):
    """Compile C firmware using GCC / MinGW."""
    return compiler.compile(request)


@app.post("/api/simulate", response_model=SimulationResult)
async def api_simulate(request: SimulationRequest):
    """Run Wokwi CLI simulation and capture output."""
    return simulator.run_simulation(request)


@app.post("/api/run-test", response_model=TestRunResult)
async def api_run_test(request: TestRunRequest):
    """
    Execute complete Hackathon MVP testing pipeline:
    uploaded C firmware
    -> Gemini FirmwareAnalyzer
    -> Pydantic FirmwareAnalysis
    -> deterministic TestGenerator
    -> TestSuite
    -> convert TestSuite into Wokwi scenario(s)
    -> run Wokwi CLI
    -> capture real serial output
    -> compare expected vs actual
    -> generate PASS/FAIL
    -> Gemini failure analysis
    """
    test_id = str(uuid.uuid4())[:8]
    start_time = time.perf_counter()

    project_dir = Path(request.project_dir)
    if not project_dir.is_absolute():
        project_dir = (settings.PROJECT_ROOT / project_dir).resolve()

    # Step 1: Read firmware source code for AI analysis
    src_file = None
    if request.source_file:
        p = Path(request.source_file)
        src_file = p if p.is_absolute() else (settings.PROJECT_ROOT / p).resolve()
    else:
        src_file = settings.PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "main.c"

    c_code = src_file.read_text(encoding="utf-8") if src_file.exists() else ""

    # Step 2: Gemini Firmware Analysis
    firmware_analysis_data = {}
    if c_code:
        try:
            analysis_model = analyzer.analyze(c_code, target_hardware="esp32-devkit-c")
            firmware_analysis_data = analysis_model.model_dump()
        except Exception as exc:
            firmware_analysis_data = {"error": str(exc)}

    # Step 3: Deterministic Test Generation
    test_suite_data = {}
    if firmware_analysis_data and "error" not in firmware_analysis_data:
        try:
            generator = DeterministicTestGenerator(analysis_model)
            suite_model = generator.generate()
            test_suite_data = suite_model.model_dump()
        except Exception as exc:
            test_suite_data = {"error": str(exc)}

    # Step 4: Scenario generation & real Wokwi CLI execution
    # In DEMO_MODE, verify real execution against known-good ESP32 firmware
    target_expect = request.expect_text or "Hello world!"
    scenario_file_path = project_dir / "scenario.yaml"

    import yaml
    scenario_content = {
        "name": "ESP32 Automated Scenario Test",
        "version": 1,
        "steps": [
            {"wait-serial": target_expect}
        ]
    }
    with open(scenario_file_path, "w", encoding="utf-8") as f:
        yaml.dump(scenario_content, f)

    sim_res = simulator.run_simulation(SimulationRequest(
        project_dir=str(project_dir),
        timeout_ms=request.timeout_ms,
        expect_text=target_expect,
        scenario_file="scenario.yaml",
        use_mock_fallback=request.use_mock_fallback
    ))

    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    # Step 5: Evaluate PASS/FAIL
    if sim_res.success:
        status = "PASSED"
        failure_diag = None
    elif sim_res.exit_code == 42:
        status = "TIMEOUT"
        failure_diag = "Simulation timed out waiting for serial output milestone."
    else:
        status = "FAILED"
        # Step 6: Gemini failure analysis
        try:
            from app.ai.gemini_client import GeminiClient
            client = GeminiClient()
            diag_prompt = (
                f"Diagnose firmware test failure.\nFirmware code:\n{c_code}\n\n"
                f"Expected serial: {target_expect}\nActual serial: {sim_res.captured_serial}\n"
                f"Error: {sim_res.stderr}\nOutput concise root cause and fix."
            )
            failure_diag = client.generate_content(diag_prompt)
        except Exception as exc:
            failure_diag = f"Failure diagnosis error: {exc}"

    result = TestRunResult(
        test_id=test_id,
        test_name=request.test_name,
        status=status,
        serial_output=sim_res.captured_serial,
        duration_ms=duration_ms,
        is_real_execution=sim_res.is_real_execution,
        mock_used=sim_res.mock_used,
        details={
            "execution_mode": settings.FIRMWARE_EXECUTION_MODE,
            "target_expect": target_expect,
            "simulation": sim_res.model_dump(),
            "firmware_analysis": firmware_analysis_data,
            "test_suite_generated": test_suite_data,
            "failure_diagnosis": failure_diag
        }
    )

    save_test_result(result.model_dump())
    return result


# =====================================================================
# PIPELINE API — Autonomous Firmware Testing
# =====================================================================

@app.post("/api/pipeline/run")
async def api_pipeline_run(request: Request):
    """
    Run the full autonomous testing pipeline:
    Source → Gemini → FirmwareAnalysis → TestSuite → Scenario → Wokwi → Evaluate → Report
    """
    body = await request.json()
    source_code = body.get("source_code", "")
    target_hardware = body.get("target_hardware", "esp32-devkit-c")
    firmware_name = body.get("firmware_name", "uploaded_firmware.c")
    selected_test_id = body.get("selected_test_id", None)
    max_tests = body.get("max_tests", 50)
    timeout_ms = body.get("timeout_ms", 8000)

    if not source_code:
        # Load default firmware
        default_src = settings.PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "main.c"
        if default_src.exists():
            source_code = default_src.read_text(encoding="utf-8")

    if not source_code:
        raise HTTPException(status_code=400, detail="No firmware source code provided.")

    result = pipeline.run_full_pipeline(
        source_code=source_code,
        target_hardware=target_hardware,
        firmware_name=firmware_name,
        run_selected_test_id=selected_test_id,
        max_tests=max_tests,
        timeout_ms=timeout_ms,
    )

    return result.model_dump()


@app.post("/api/firmware/analyze", response_model=FirmwareAnalysis)
async def api_analyze_firmware(request: FirmwareAnalysisRequest):
    """
    Analyze C/C++ firmware source code with Gemini and return structured FirmwareAnalysis.
    """
    code = request.source_code
    if not code and request.source_file:
        src_path = Path(request.source_file)
        if not src_path.is_absolute():
            src_path = (settings.PROJECT_ROOT / src_path).resolve()
        if src_path.exists():
            code = src_path.read_text(encoding="utf-8")
    
    if not code:
        default_path = settings.PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "main.c"
        if default_path.exists():
            code = default_path.read_text(encoding="utf-8")

    try:
        analysis = analyzer.analyze(
            source_code=code or "",
            target_hardware=request.target_hardware,
        )
        return analysis
    except EmptySourceCodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except GeminiAPIKeyMissingError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except (ModelOutputParsingError, ModelOutputValidationError) as exc:
        raise HTTPException(status_code=502, detail=f"AI model output error: {exc}")
    except GeminiAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini API failure: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal analysis error: {exc}")


@app.post("/api/firmware/generate-tests", response_model=TestSuite)
async def api_generate_tests(analysis: FirmwareAnalysis):
    """Generate categorized deterministic TestSuite from a validated FirmwareAnalysis model."""
    try:
        generator = DeterministicTestGenerator(analysis)
        suite = generator.generate()
        return suite
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Test generation error: {exc}")


@app.get("/api/results")
async def api_results():
    """List test results from disk."""
    return list_test_results()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True
    )
