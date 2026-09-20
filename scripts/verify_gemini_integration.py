"""
Step 4: Verify Real Gemini Integration Script
Sends firmware/examples/fan_controller/main.c to Google Gemini, validates
output against FirmwareAnalysis Pydantic model, generates deterministic TestSuite,
and writes artifacts without exposing secrets.
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.config import settings
from app.ai.gemini_client import GeminiClient
from app.ai.analyzer import FirmwareAnalyzer
from app.tests.generator import DeterministicTestGenerator
from app.models.firmware import FirmwareAnalysis


def run_verification():
    print("==================================================")
    print("STEP 4: REAL GEMINI INTEGRATION VERIFICATION")
    print("==================================================")

    # 1. Confirm GEMINI_API_KEY is loaded from .env without printing key
    is_configured = settings.has_gemini_key()
    status_str = "CONFIGURED" if is_configured else "NOT CONFIGURED"
    print(f"GEMINI_API_KEY: {status_str}")

    if not is_configured:
        print("\n==================================================")
        print("FINAL REPORT:")
        print("GEMINI CONFIGURED: NO")
        print("GEMINI REQUEST: FAIL (GEMINI_API_KEY is not configured in .env)")
        print(f"MODEL: {settings.GEMINI_MODEL}")
        print("FIRMWARE ANALYSIS VALID: NO")
        print("GENERATED TEST COUNT: 0")
        print("TEST CATEGORIES: None")
        print("ANALYSIS FILE: None")
        print("TEST SUITE FILE: None")
        print("==================================================")
        return 1

    # 2. Confirm model and initialize analyzer
    print(f"MODEL: {settings.GEMINI_MODEL}")
    client = GeminiClient(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL, timeout=settings.GEMINI_TIMEOUT_SECONDS)
    analyzer = FirmwareAnalyzer(client=client)

    # 3. Read firmware source code
    source_path = PROJECT_ROOT / "firmware" / "examples" / "fan_controller" / "main.c"
    if not source_path.exists():
        print(f"ERROR: Firmware source file not found: {source_path}")
        return 1

    source_code = source_path.read_text(encoding="utf-8")
    target_hardware = "ESP32 DevKit-C"
    print(f"Sending {source_path.name} to Gemini ({settings.GEMINI_MODEL}) for target '{target_hardware}'...")

    # 4. Invoke real Gemini request
    try:
        analysis = analyzer.analyze(source_code=source_code, target_hardware=target_hardware)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"Gemini API request failed: {type(exc).__name__}: {exc}")
        print("\n==================================================")
        print("FINAL REPORT:")
        print("GEMINI CONFIGURED: YES")
        print("GEMINI REQUEST: FAIL")
        print(f"MODEL: {settings.GEMINI_MODEL}")
        print("FIRMWARE ANALYSIS VALID: NO")
        print("GENERATED TEST COUNT: 0")
        print("TEST CATEGORIES: None")
        print("ANALYSIS FILE: None")
        print("TEST SUITE FILE: None")
        print("==================================================")
        return 1

    # 5. Save returned analysis
    results_dir = settings.get_results_path()
    analysis_file = results_dir / "gemini_fan_controller_analysis.json"
    analysis_json = analysis.model_dump_json(indent=2)
    analysis_file.write_text(analysis_json, encoding="utf-8")
    print(f"Analysis saved to: {analysis_file}")

    # 6. Validate with FirmwareAnalysis
    is_valid = isinstance(analysis, FirmwareAnalysis)

    # 7. Run deterministic TestGenerator
    test_gen = DeterministicTestGenerator(analysis)
    test_suite = test_gen.generate()

    suite_file = results_dir / "gemini_generated_test_suite.json"
    suite_file.write_text(test_suite.model_dump_json(indent=2), encoding="utf-8")
    print(f"Test suite saved to: {suite_file}")

    # 8. Extract categories
    categories = sorted(list({t.category.value if hasattr(t.category, "value") else str(t.category) for t in test_suite.test_cases}))

    print("\n==================================================")
    print("FINAL REPORT:")
    print("GEMINI CONFIGURED: YES")
    print("GEMINI REQUEST: SUCCESS")
    print(f"MODEL: {settings.GEMINI_MODEL}")
    print(f"FIRMWARE ANALYSIS VALID: {'YES' if is_valid else 'NO'}")
    print(f"GENERATED TEST COUNT: {len(test_suite.test_cases)}")
    print(f"TEST CATEGORIES: {', '.join(categories)}")
    print(f"ANALYSIS FILE: {analysis_file.relative_to(PROJECT_ROOT).as_posix()}")
    print(f"TEST SUITE FILE: {suite_file.relative_to(PROJECT_ROOT).as_posix()}")
    print("==================================================")
    return 0


if __name__ == "__main__":
    sys.exit(run_verification())
