"""
Test Case and Test Suite Data Models
Structured representation of generated firmware test cases.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class TestCategory(str, Enum):
    NORMAL = "NORMAL"
    BOUNDARY = "BOUNDARY"
    ABNORMAL = "ABNORMAL"
    SENSOR_FAILURE = "SENSOR_FAILURE"
    STATE_TRANSITION = "STATE_TRANSITION"
    COMMUNICATION_FAILURE = "COMMUNICATION_FAILURE"
    UNEXPECTED_INPUT = "UNEXPECTED_INPUT"
    COMBINATION = "COMBINATION"


TestCategory.__test__ = False


class TestPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


TestPriority.__test__ = False


class TestCase(BaseModel):
    """
    Structured representation of an individual firmware test case.
    Set __test__ = False to prevent pytest from misidentifying it as a test class.
    """
    __test__ = False

    id: str = Field(..., description="Unique test case identifier (e.g., 'TC_NORM_001')")
    name: str = Field(..., description="Human-readable title for the test case")
    category: TestCategory = Field(..., description="Classification category of the test")
    description: str = Field(..., description="Detailed description of the test scenario and intent")
    priority: TestPriority = Field(default=TestPriority.MEDIUM, description="Execution priority")
    preconditions: List[str] = Field(default_factory=list, description="Required system states prior to execution")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Test input parameters or sensor readings")
    actions: List[str] = Field(default_factory=list, description="Step-by-step actions executed during the test")
    expected_outputs: Dict[str, Any] = Field(default_factory=dict, description="Expected pin states or values")
    expected_behavior: str = Field(..., description="Expected system behavior and state response")
    failure_conditions: List[str] = Field(default_factory=list, description="Conditions that signify test failure")
    hardware_requirements: Dict[str, Any] = Field(default_factory=dict, description="Required target board, pins, and peripherals")
    expected_serial_log: Optional[str] = Field(None, description="Expected log string or pattern in serial output")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context or traceability metadata")


class TestSuite(BaseModel):
    """
    Collection of generated test cases for a firmware project.
    """
    __test__ = False

    firmware_name: str = Field(..., description="Name of the firmware under test")
    target_hardware: str = Field(..., description="Target hardware platform or board")
    test_cases: List[TestCase] = Field(default_factory=list, description="List of generated test cases")
    total_tests: int = Field(default=0, description="Total count of test cases")
    categories_count: Dict[str, int] = Field(default_factory=dict, description="Test counts broken down by category")

    def add_test_case(self, test_case: TestCase) -> None:
        """Add a test case and update count metrics."""
        self.test_cases.append(test_case)
        self.total_tests = len(self.test_cases)
        cat_key = test_case.category.value if isinstance(test_case.category, TestCategory) else str(test_case.category)
        self.categories_count[cat_key] = self.categories_count.get(cat_key, 0) + 1

    def filter_by_category(self, category: Union[TestCategory, str]) -> List[TestCase]:
        """Return all test cases matching the specified category."""
        target_val = category.value if isinstance(category, TestCategory) else category
        return [
            tc for tc in self.test_cases
            if (tc.category.value if isinstance(tc.category, TestCategory) else str(tc.category)) == target_val
        ]

    def get_test_by_id(self, test_id: str) -> Optional[TestCase]:
        """Find a test case by unique ID."""
        for tc in self.test_cases:
            if tc.id == test_id:
                return tc
        return None

    def to_json_file(self, file_path: Union[str, Path], indent: int = 2) -> None:
        """Write test suite to JSON file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=indent))

    @classmethod
    def from_json_file(cls, file_path: Union[str, Path]) -> "TestSuite":
        """Load test suite from JSON file."""
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())
