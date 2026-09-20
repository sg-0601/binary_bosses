"""
Unit Tests for Application Configuration, Toolchain Resolution, and Secrets Security
Verifies Pydantic settings loading, toolchain path resolution, distinction between
CONFIGURED and VERIFIED states, and protection of API keys/tokens.
"""

import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from app.utils.config import Settings
from app.ai.gemini_client import GeminiClient, GeminiAPIKeyMissingError


def test_default_settings():
    """Verify default settings values when initialized."""
    s = Settings()
    assert s.WOKWI_CLI_PATH == "./wokwi-cli.exe"
    assert s.ARDUINO_CLI_PATH == "./bin/arduino-cli.exe"
    assert s.ESP32_FQBN == "esp32:esp32:esp32"
    assert s.ARDUINO_CORE_NAME == "esp32:esp32"
    assert s.GEMINI_MODEL in ("gemini-3.5-flash", "gemini-3.6-flash", "gemini-2.5-flash", "gemini-3.1-flash-lite")
    assert s.APP_PORT == 8000
    assert s.APP_HOST == "127.0.0.1"


def test_settings_environment_override(monkeypatch):
    """Verify environment variables override default settings."""
    monkeypatch.setenv("WOKWI_TIMEOUT_MS", "12000")
    monkeypatch.setenv("ESP32_FQBN", "esp32:esp32:esp32s3")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")

    s = Settings()
    assert s.WOKWI_TIMEOUT_MS == 12000
    assert s.ESP32_FQBN == "esp32:esp32:esp32s3"
    assert s.GEMINI_MODEL == "gemini-1.5-pro"


def test_results_path_creation(tmp_path, monkeypatch):
    """Verify get_results_path creates and returns the directory as Path."""
    custom_dir = str(tmp_path / "custom_results")
    monkeypatch.setenv("TEST_RESULTS_DIR", custom_dir)

    s = Settings()
    path = s.get_results_path()
    assert path.exists()
    assert path.is_dir()


def test_secret_masking():
    """Verify Wokwi token and Gemini key are masked properly."""
    s = Settings(
        WOKWI_CLI_TOKEN="wok_1234567890abcdef",
        GEMINI_API_KEY="AIzaSyA1234567890abcdef"
    )

    assert s.masked_wokwi_token == "wok_...cdef"
    assert s.masked_gemini_key == "AIza...cdef"

    # Verify repr does not leak full secrets
    rep = repr(s)
    assert "wok_1234567890abcdef" not in rep
    assert "AIzaSyA1234567890abcdef" not in rep
    assert "wok_...cdef" in rep
    assert "AIza...cdef" in rep


def test_empty_secret_masking():
    """Verify empty secrets produce empty masked strings."""
    s = Settings(WOKWI_CLI_TOKEN="", GEMINI_API_KEY="")
    assert s.masked_wokwi_token == ""
    assert s.masked_gemini_key == ""


def test_has_token_and_has_key():
    """Verify distinction between configured tokens and empty tokens."""
    s_empty = Settings(WOKWI_CLI_TOKEN="", GEMINI_API_KEY="")
    assert not s_empty.has_wokwi_token()
    assert not s_empty.has_gemini_key()

    s_configured = Settings(WOKWI_CLI_TOKEN="some_token", GEMINI_API_KEY="some_key")
    assert s_configured.has_wokwi_token()
    assert s_configured.has_gemini_key()


def test_gemini_client_missing_key_error():
    """Verify GeminiClient raises clean error without leaking secrets when key is absent."""
    client = GeminiClient(api_key="")
    assert not client.is_configured

    with pytest.raises(GeminiAPIKeyMissingError) as exc_info:
        client.generate_content(prompt="Analyze this")

    assert "GEMINI_API_KEY" in str(exc_info.value)
    # Ensure error message does not contain arbitrary secrets
    assert "None" not in str(exc_info.value)


def test_toolchain_resolution_methods():
    """Verify toolchain resolution methods return valid string paths."""
    s = Settings()

    wokwi_exe = s.get_wokwi_executable()
    assert isinstance(wokwi_exe, str)
    assert len(wokwi_exe) > 0

    arduino_exe = s.get_arduino_cli_executable()
    assert isinstance(arduino_exe, str)
    assert len(arduino_exe) > 0

    gcc_exe = s.get_gcc_executable()
    assert isinstance(gcc_exe, str)
    assert len(gcc_exe) > 0


def test_toolchain_installed_checks_mocked():
    """Verify is_wokwi_installed, is_arduino_cli_installed, and is_esp32_core_installed."""
    s = Settings()

    with patch("subprocess.run") as mock_run:
        # Mock successful version output
        mock_run.return_value = MagicMock(returncode=0, stdout="wokwi-cli 0.1.0")
        assert s.is_wokwi_installed() is True

        mock_run.return_value = MagicMock(returncode=0, stdout="arduino-cli Version: 1.4.1")
        assert s.is_arduino_cli_installed() is True

        # Mock core list with esp32:esp32
        mock_run.return_value = MagicMock(returncode=0, stdout="esp32:esp32 3.3.12 esp32")
        assert s.is_esp32_core_installed() is True

        # Mock core list without esp32
        mock_run.return_value = MagicMock(returncode=0, stdout="No platforms installed.")
        assert s.is_esp32_core_installed() is False

        # Mock command failure
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert s.is_wokwi_installed() is False


def test_gitignore_protects_env():
    """Verify that .gitignore exists and explicitly ignores .env to protect secrets."""
    gitignore_path = Path(__file__).resolve().parent.parent.parent / ".gitignore"
    assert gitignore_path.exists(), "firmware-tester/.gitignore must exist"
    
    content = gitignore_path.read_text(encoding="utf-8")
    assert ".env" in content
    assert "*.env" in content
    assert "test_results/" in content
