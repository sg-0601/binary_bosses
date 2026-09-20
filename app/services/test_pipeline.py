"""
Test Pipeline Orchestrator
Coordinates the full autonomous firmware testing flow end-to-end.
"""

import uuid
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.firmware import FirmwareAnalysis
from app.models.test_case import TestCase, TestSuite
from app.models.schemas import SimulationRequest
from app.tests.generator import DeterministicTestGenerator
from app.tests.evaluator import TestEvaluator, TestResult, evaluator
from app.simulator.scenario_generator import ScenarioGenerator, scenario_generator
from app.simulator.wokwi_runner import WokwiRunner, simulator
from app.services.artifact_provider import ExecutionArtifactProvider, artifact_provider
from app.ai.analyzer import FirmwareAnalyzer, analyzer
from app.ai.failure_analyzer import FailureAnalyzer, failure_analyzer
from app.utils.config import settings


class PipelineResult(BaseModel):
    """Complete result from an autonomous test pipeline run."""
    run_id: str = Field(..., description="Unique pipeline run ID")
    execution_mode: str = Field("demo", description="Execution mode used")
    firmware_name: str = Field("", description="Uploaded firmware filename")
    trace: List[str] = Field(default_factory=list, description="Step-by-step execution trace")
    firmware_analysis: Optional[Dict[str, Any]] = Field(None, description="Gemini firmware analysis")
    test_suite: Optional[Dict[str, Any]] = Field(None, description="Generated test suite")
    test_results: List[Dict[str, Any]] = Field(default_factory=list, description="Individual test results")
    summary: Dict[str, int] = Field(default_factory=dict, description="Aggregate: PASS/FAIL/ERROR/MOCK counts")
    duration_ms: float = Field(0.0, description="Total pipeline duration in ms")
    demo_notice: str = Field(
        default="DEMO MODE: Firmware source is analyzed by AI. "
                "Simulation uses a known-good precompiled ESP32 demo artifact.",
        description="DEMO MODE transparency notice")
    errors: List[str] = Field(default_factory=list, description="Pipeline-level errors")


class TestPipeline:
    """
    Orchestrates the autonomous firmware testing pipeline:
    
    Source Code → Gemini Analysis → FirmwareAnalysis → TestGenerator → TestSuite
    → ScenarioGenerator → WokwiRunner → Evaluator → FailureAnalyzer → Report
    """

    def __init__(self):
        self.analyzer = analyzer
        self.artifact_provider = artifact_provider
        self.scenario_gen = scenario_generator
        self.wokwi_runner = simulator
        self.evaluator = evaluator
        self.failure_analyzer = failure_analyzer

    def run_full_pipeline(
        self,
        source_code: str,
        target_hardware: str = "esp32-devkit-c",
        firmware_name: str = "uploaded_firmware.c",
        run_selected_test_id: Optional[str] = None,
        max_tests: int = 50,
        timeout_ms: int = 8000,
    ) -> PipelineResult:
        """
        Execute the complete autonomous testing pipeline.
        
        If run_selected_test_id is provided, only that test is executed.
        Otherwise, all tests up to max_tests are executed.
        """
        run_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()
        trace: List[str] = []
        errors: List[str] = []

        result = PipelineResult(
            run_id=run_id,
            execution_mode=settings.FIRMWARE_EXECUTION_MODE,
            firmware_name=firmware_name,
        )

        # Step 1: Validate execution environment
        trace.append(f"[1] Pipeline started (run_id={run_id}, mode={settings.FIRMWARE_EXECUTION_MODE})")

        if not self.wokwi_runner.has_token():
            errors.append("WOKWI_CLI_TOKEN is not configured. Real execution is required.")
            trace.append("[ERROR] WOKWI_CLI_TOKEN missing — cannot proceed")
            result.trace = trace
            result.errors = errors
            result.duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return result

        if not self.artifact_provider.validate():
            missing = self.artifact_provider.get_missing_artifacts()
            errors.append(f"Demo artifacts missing: {missing}")
            trace.append(f"[ERROR] Missing demo artifacts: {missing}")
            result.trace = trace
            result.errors = errors
            result.duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return result

        # Step 2: Gemini Firmware Analysis
        trace.append("[2] Analyzing firmware with Gemini AI...")
        try:
            analysis = self.analyzer.analyze(source_code=source_code, target_hardware=target_hardware)
            result.firmware_analysis = analysis.model_dump()
            trace.append(f"[3] FirmwareAnalysis validated: {analysis.firmware_name}")
        except Exception as exc:
            errors.append(f"Firmware analysis failed: {exc}")
            trace.append(f"[ERROR] Gemini analysis failed: {exc}")
            result.trace = trace
            result.errors = errors
            result.duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return result

        # Step 3: Deterministic Test Generation
        trace.append("[4] Generating deterministic test suite...")
        try:
            generator = DeterministicTestGenerator(analysis)
            suite = generator.generate()
            result.test_suite = suite.model_dump()
            trace.append(f"[5] TestSuite generated: {suite.total_tests} tests across {len(suite.categories_count)} categories")
        except Exception as exc:
            errors.append(f"Test generation failed: {exc}")
            trace.append(f"[ERROR] Test generation failed: {exc}")
            result.trace = trace
            result.errors = errors
            result.duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return result

        # Step 4: Select tests to run
        if run_selected_test_id:
            selected = suite.get_test_by_id(run_selected_test_id)
            if not selected:
                errors.append(f"Test ID '{run_selected_test_id}' not found in suite")
                trace.append(f"[ERROR] Test {run_selected_test_id} not found")
                result.trace = trace
                result.errors = errors
                result.duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return result
            tests_to_run = [selected]
        else:
            tests_to_run = suite.test_cases[:max_tests]

        trace.append(f"[6] Selected {len(tests_to_run)} test(s) for execution")

        # Step 5: Execute each test
        run_dir = settings.get_results_path() / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        project_dir = self.artifact_provider.get_project_dir()

        test_results: List[Dict[str, Any]] = []
        counts = {"PASS": 0, "FAIL": 0, "ERROR": 0, "MOCK": 0}

        for i, tc in enumerate(tests_to_run, 1):
            trace.append(f"[{6+i}] Running test {tc.id}: {tc.name}")
            tr = self._run_single_test(
                test_case=tc,
                project_dir=project_dir,
                run_dir=run_dir,
                timeout_ms=timeout_ms,
                source_code=source_code,
                analysis=analysis,
            )
            test_results.append(tr.model_dump())
            counts[tr.status] = counts.get(tr.status, 0) + 1
            trace.append(f"    → {tr.status}: {tr.expected[:60] if tr.expected else 'N/A'}")

        result.test_results = test_results
        result.summary = counts
        result.trace = trace
        result.errors = errors
        result.duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return result

    def _run_single_test(
        self,
        test_case: TestCase,
        project_dir: Path,
        run_dir: Path,
        timeout_ms: int,
        source_code: str = "",
        analysis: Optional[FirmwareAnalysis] = None,
    ) -> TestResult:
        """Execute a single test case through the Wokwi pipeline."""

        # Generate scenario
        try:
            scenario = self.scenario_gen.generate(
                test_case=test_case,
                run_dir=run_dir,
                timeout_ms=timeout_ms,
            )
        except Exception as exc:
            return TestResult(
                test_id=test_case.id,
                name=test_case.name,
                category=test_case.category.value if hasattr(test_case.category, 'value') else str(test_case.category),
                status="ERROR",
                expected=test_case.expected_serial_log or "",
                observed=f"Scenario generation failed: {exc}",
                failed_conditions=[f"Scenario generation error: {exc}"],
            )

        # Run Wokwi with generated scenario in isolated per-test directory
        sim_request = SimulationRequest(
            project_dir=scenario.project_dir,
            timeout_ms=timeout_ms,
            scenario_file="scenario.yaml",
            use_mock_fallback=False,  # NEVER use mock in pipeline
        )

        sim_result = self.wokwi_runner.run_simulation(sim_request)

        # Deterministic evaluation
        test_result = self.evaluator.evaluate(test_case, sim_result)

        # Failure analysis if FAIL
        if test_result.status == "FAIL" and source_code:
            try:
                fa = self.failure_analyzer.analyze_failure(
                    test_id=test_case.id,
                    test_name=test_case.name,
                    expected_behavior=test_case.expected_serial_log or test_case.expected_behavior,
                    observed_serial=sim_result.captured_serial[:2000] if sim_result.captured_serial else "",
                    firmware_source=source_code[:3000],
                    firmware_analysis_summary=analysis.firmware_name if analysis else "",
                    wokwi_errors=sim_result.stderr[:500] if sim_result.stderr else "",
                )
                test_result.failure_analysis = fa.model_dump()
            except Exception:
                pass  # Failure analysis is optional

        return test_result


pipeline = TestPipeline()
