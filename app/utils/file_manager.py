import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from app.utils.config import settings


def save_test_result(data: Dict[str, Any]) -> str:
    """Save a test result dictionary to test_results/ as JSON."""
    results_dir = settings.get_results_path()
    test_id = data.get("test_id") or str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"result_{timestamp}_{test_id}.json"
    file_path = results_dir / filename

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return str(file_path)


def list_test_results() -> List[Dict[str, Any]]:
    """List all saved test results sorted by modification time (latest first)."""
    results_dir = settings.get_results_path()
    results = []
    
    for file_path in sorted(results_dir.glob("result_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                content["_filename"] = file_path.name
                results.append(content)
        except Exception:
            continue

    return results
