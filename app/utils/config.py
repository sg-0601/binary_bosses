"""
Application Configuration and Environment Settings
Centralized configuration for Wokwi CLI, Arduino CLI, GCC, Gemini API, and Server.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized configuration for the Autonomous Embedded Firmware Testing System.
    Loads from .env, environment variables, or defaults.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Base filesystem paths
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    APP_DIR: Path = Path(__file__).resolve().parent.parent

    # -------------------------------------------------------------------------
    # Wokwi CLI & Cloud Simulation Configuration
    # -------------------------------------------------------------------------
    WOKWI_CLI_TOKEN: str = ""
    WOKWI_CLI_PATH: str = "./wokwi-cli.exe"
    WOKWI_TIMEOUT_MS: int = 5000

    # -------------------------------------------------------------------------
    # Arduino CLI & Embedded Toolchain Configuration
    # -------------------------------------------------------------------------
    ARDUINO_CLI_PATH: str = "./bin/arduino-cli.exe"
    ESP32_FQBN: str = "esp32:esp32:esp32"
    ARDUINO_CORE_NAME: str = "esp32:esp32"

    # -------------------------------------------------------------------------
    # Host GCC/MinGW Compiler Configuration
    # -------------------------------------------------------------------------
    GCC_PATH: str = "gcc"
    GCC_DEFAULT_FLAGS: List[str] = ["-Wall", "-O2"]

    # -------------------------------------------------------------------------
    # Execution Mode: demo (precompiled artifact) or compile (on-demand build)
    # -------------------------------------------------------------------------
    FIRMWARE_EXECUTION_MODE: str = "demo"

    # -------------------------------------------------------------------------
    # Google Gemini AI Configuration
    # -------------------------------------------------------------------------
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_TIMEOUT_SECONDS: float = 90.0

    # -------------------------------------------------------------------------
    # Server, Database, and Artifact Storage Settings
    # -------------------------------------------------------------------------
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    TEST_RESULTS_DIR: str = "./test_results"
    DATABASE_URL: str = "sqlite:///./firmware_tester.db"

    # -------------------------------------------------------------------------
    # Helper Resolution Methods
    # -------------------------------------------------------------------------
    def get_wokwi_executable(self) -> str:
        """Resolve absolute path to wokwi-cli executable."""
        # 1. System PATH or binary name (standard in Docker / Linux environments)
        found = shutil.which(self.WOKWI_CLI_PATH) or shutil.which("wokwi-cli") or shutil.which("wokwi-cli.exe")
        if found:
            return found

        # 2. Direct path relative to PROJECT_ROOT
        direct_path = (self.PROJECT_ROOT / self.WOKWI_CLI_PATH).resolve()
        if direct_path.exists() and direct_path.is_file():
            return str(direct_path)

        # 3. Local in PROJECT_ROOT
        local_wokwi = self.PROJECT_ROOT / "wokwi-cli.exe"
        if local_wokwi.exists() and local_wokwi.is_file():
            return str(local_wokwi)

        return self.WOKWI_CLI_PATH

    def is_wokwi_installed(self) -> bool:
        """Check if wokwi-cli is installed and responds to --version."""
        exe = self.get_wokwi_executable()
        try:
            res = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False

    def has_wokwi_token(self) -> bool:
        """Check if Wokwi CI token is set in environment or config."""
        token = self.WOKWI_CLI_TOKEN or os.environ.get("WOKWI_CLI_TOKEN", "")
        return bool(token.strip())

    def get_gcc_executable(self) -> str:
        """Resolve path to GCC executable."""
        found = shutil.which(self.GCC_PATH)
        return found if found else self.GCC_PATH

    def is_gcc_installed(self) -> bool:
        """Check if GCC compiler is installed and functional."""
        exe = self.get_gcc_executable()
        try:
            res = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False

    def get_arduino_cli_executable(self) -> str:
        """Resolve path to arduino-cli executable."""
        # 1. Direct path relative to PROJECT_ROOT
        direct_path = (self.PROJECT_ROOT / self.ARDUINO_CLI_PATH).resolve()
        if direct_path.exists() and direct_path.is_file():
            return str(direct_path)

        # 2. In ./bin subdirectory of PROJECT_ROOT
        bin_path = (self.PROJECT_ROOT / "bin" / "arduino-cli.exe").resolve()
        if bin_path.exists() and bin_path.is_file():
            return str(bin_path)

        # 3. System PATH
        found = shutil.which(self.ARDUINO_CLI_PATH) or shutil.which("arduino-cli") or shutil.which("arduino-cli.exe")
        if found:
            return found

        return str(direct_path)

    def is_arduino_cli_installed(self) -> bool:
        """Check if arduino-cli is executable and responds to version command."""
        exe = self.get_arduino_cli_executable()
        try:
            res = subprocess.run([exe, "version"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False

    def is_esp32_core_installed(self) -> bool:
        """Check if esp32:esp32 platform core is installed in arduino-cli."""
        exe = self.get_arduino_cli_executable()
        try:
            res = subprocess.run([exe, "core", "list"], capture_output=True, text=True, timeout=10)
            return res.returncode == 0 and ("esp32:esp32" in res.stdout or "esp32" in res.stdout)
        except Exception:
            return False

    def has_gemini_key(self) -> bool:
        """Check if Gemini API key is configured."""
        key = self.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        return bool(key.strip())

    @property
    def masked_wokwi_token(self) -> str:
        """Return masked representation of WOKWI_CLI_TOKEN (safe for logging/display)."""
        token = self.WOKWI_CLI_TOKEN or os.environ.get("WOKWI_CLI_TOKEN", "")
        if not token:
            return ""
        if len(token) <= 8:
            return "***"
        return f"{token[:4]}...{token[-4:]}"

    @property
    def masked_gemini_key(self) -> str:
        """Return masked representation of GEMINI_API_KEY (safe for logging/display)."""
        key = self.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            return ""
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    def __repr__(self) -> str:
        """Safe string representation of Settings without leaking plain-text secrets."""
        data = self.model_dump()
        if data.get("WOKWI_CLI_TOKEN"):
            data["WOKWI_CLI_TOKEN"] = self.masked_wokwi_token
        if data.get("GEMINI_API_KEY"):
            data["GEMINI_API_KEY"] = self.masked_gemini_key
        return f"Settings({data})"

    def __str__(self) -> str:
        return self.__repr__()

    def get_results_path(self) -> Path:
        """Ensure and return the test results directory."""
        path = (self.PROJECT_ROOT / self.TEST_RESULTS_DIR).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
