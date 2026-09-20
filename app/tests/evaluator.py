"""
Deterministic Test Evaluator
Compares TestCase expectations against SimulationResult to produce PASS/FAIL.

Gemini does NOT determine PASS/FAIL. This is purely deterministic.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.test_case import TestCase
from app.models.schemas import SimulationResult


class TestResult(BaseModel):
    """Deterministic result of evaluating a TestCase against simulation output."""
    __test__ = False

    test_id: str = Field(..., description="Test case ID")
    name: str = Field(..., description="Test case name")
    category: str = Field(..., description="Test category")
    status: str = Field(..., description="PASS, FAIL, ERROR, or MOCK")
    expected: str = Field("", description="Expected serial pattern or behavior")
    observed: str = Field("", description="Observed serial output (truncated)")
    matched_conditions: List[str] = Field(default_factory=list, description="Conditions that matched")
    failed_conditions: List[str] = Field(default_factory=list, description="Conditions that failed")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Raw evidence data")
    duration_ms: float = Field(0.0, description="Execution duration in ms")
    failure_analysis: Optional[Dict[str, Any]] = Field(None, description="AI failure analysis if applicable")
    wokwi_exit_code: int = Field(-1, description="Wokwi CLI exit code")


class TestEvaluator:
    """
    Deterministically evaluates test case expectations against simulation results.
    
    Rules:
    - Mock execution NEVER produces PASS → always MOCK status
    - Missing resources → ERROR status
    - Real execution → deterministic PASS/FAIL based on serial pattern matching and exit code
    """
    __test__ = False

    def evaluate(self, test_case: TestCase, sim_result: SimulationResult) -> TestResult:
        """
        Compare TestCase expectations against SimulationResult.

        Returns TestResult with deterministic status.
        """
        # Rule 1: Mock execution can NEVER produce PASS
        if sim_result.mock_used:
            return TestResult(
                test_id=test_case.id,
                name=test_case.name,
                category=test_case.category.value if hasattr(test_case.category, 'value') else str(test_case.category),
                status="MOCK",
                expected=test_case.expected_serial_log or test_case.expected_behavior,
                observed=sim_result.captured_serial[:500] if sim_result.captured_serial else "",
                failed_conditions=["Mock execution used — result is not authoritative"],
                evidence={"mock_used": True, "is_real_execution": False},
                duration_ms=sim_result.duration_ms,
                wokwi_exit_code=sim_result.exit_code,
            )

        # Rule 2: Non-real execution → ERROR
        if not sim_result.is_real_execution:
            return TestResult(
                test_id=test_case.id,
                name=test_case.name,
                category=test_case.category.value if hasattr(test_case.category, 'value') else str(test_case.category),
                status="ERROR",
                expected=test_case.expected_serial_log or test_case.expected_behavior,
                observed=sim_result.stderr[:500] if sim_result.stderr else "",
                failed_conditions=["Execution was not real Wokwi — check configuration"],
                evidence={"is_real_execution": False, "stderr": sim_result.stderr[:500]},
                duration_ms=sim_result.duration_ms,
                wokwi_exit_code=sim_result.exit_code,
            )

        # Rule 3: Real Wokwi execution — deterministic evaluation
        matched: List[str] = []
        failed: List[str] = []

        # Check Wokwi exit code
        if sim_result.exit_code == 0:
            matched.append("Wokwi CLI exited with code 0 (scenario passed)")
        elif sim_result.exit_code == 42:
            failed.append("Wokwi simulation timed out (exit code 42)")
        else:
            failed.append(f"Wokwi CLI exited with error code {sim_result.exit_code}")

        # Check expected serial pattern
        expected_pattern = test_case.expected_serial_log or ""
        observed = sim_result.captured_serial or ""

        if expected_pattern:
            if expected_pattern in observed:
                matched.append(f"Serial pattern '{expected_pattern}' found in output")
            else:
                failed.append(f"Serial pattern '{expected_pattern}' NOT found in output")

        # Determine status
        if sim_result.exit_code not in (0, 42) and sim_result.stderr and "ERROR" in sim_result.stderr.upper():
            status = "ERROR"
        elif failed:
            status = "FAIL"
        else:
            status = "PASS"

        return TestResult(
            test_id=test_case.id,
            name=test_case.name,
            category=test_case.category.value if hasattr(test_case.category, 'value') else str(test_case.category),
            status=status,
            expected=expected_pattern or test_case.expected_behavior,
            observed=observed[:1000] if observed else "",
            matched_conditions=matched,
            failed_conditions=failed,
            evidence={
                "wokwi_exit_code": sim_result.exit_code,
                "is_real_execution": sim_result.is_real_execution,
                "serial_length": len(observed),
                "duration_ms": sim_result.duration_ms,
            },
            duration_ms=sim_result.duration_ms,
            wokwi_exit_code=sim_result.exit_code,
        )


evaluator = TestEvaluator()
