# Autonomous Embedded Firmware Testing System

A comprehensive, automated test generation and execution platform for **Problem Statement 3 (AI Agent for Autonomous Embedded Firmware Testing)**.

The system bridges AI-driven firmware understanding, deterministic test generation, embedded cross-compilation, and headless hardware simulation:

```
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│ C/C++ Firmware Source   │ ──► │ Google Gemini AI Model  │ ──► │ Structured Pydantic     │
│ (e.g. Fan Controller)   │     │ (Firmware Analysis)     │     │ FirmwareAnalysis Model  │
└─────────────────────────┘     └─────────────────────────┘     └───────────┬─────────────┘
                                                                            │
┌─────────────────────────┐     ┌─────────────────────────┐                 │
│ Headless Simulation     │ ◄── │ Deterministic Test Gen  │ ◄───────────────┘
│ (Wokwi CLI / Hardware)  │     │ (8 Test Categories)     │
└───────────┬─────────────┘     └─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│ Serial Output & Logs    │ ──► Automated Assertion & Evaluation
└─────────────────────────┘
```

---

## 📁 Project Structure

```
firmware-tester/
├── app/
│   ├── main.py                  # FastAPI server & diagnostic health endpoints
│   ├── ai/                      # Gemini AI integration layer
│   │   ├── __init__.py
│   │   ├── analyzer.py          # Strict FirmwareAnalysis generation & parsing
│   │   ├── gemini_client.py     # Isolated Gemini REST API client
│   │   └── prompts.py           # Structured analysis system & user prompts
│   ├── models/                  # Pydantic v2 domain schemas
│   │   ├── __init__.py
│   │   ├── firmware.py          # 17-field FirmwareAnalysis data models
│   │   ├── test_case.py         # TestCase, TestSuite, TestCategory models
│   │   └── schemas.py           # API request/response & HealthStatus schemas
│   ├── tests/                   # Test generation & verification suite
│   │   ├── __init__.py
│   │   ├── generator.py         # Deterministic multi-category test generator
│   │   ├── test_config.py       # Configuration & secrets protection tests
│   │   ├── test_firmware_models.py # Pydantic model validation tests
│   │   ├── test_gemini_analyzer.py # Gemini analyzer & golden test suite
│   │   ├── test_pipeline.py     # End-to-end compilation & simulation tests
│   │   └── test_test_generator.py  # Deterministic test generator tests
│   ├── simulator/               # Wokwi simulation runner & serial log capture
│   │   ├── __init__.py
│   │   └── wokwi_runner.py
│   ├── compiler/                # Host-side GCC / MinGW compiler
│   │   ├── __init__.py
│   │   └── gcc_compiler.py
│   ├── templates/               # Jinja2 web dashboard
│   │   └── index.html
│   └── utils/                   # Settings, paths, and persistence
│       ├── __init__.py
│       ├── config.py            # Centralized Pydantic Settings & resolution
│       └── file_manager.py      # Test run artifact storage
├── bin/
│   └── arduino-cli.exe          # Arduino CLI Windows executable (v1.4.1)
├── firmware/
│   └── examples/
│       └── fan_controller/      # Reference ESP32 fan controller firmware
│           ├── main.c
│           └── firmware_analysis.json  # Golden reference analysis
├── wokwi/
│   └── projects/
│       └── fan_controller/      # Wokwi simulation configuration
│           ├── diagram.json     # Hardware schematic & wiring
│           ├── wokwi.toml       # Board & binary mapping
│           └── scenario.yaml    # Simulation stimulus
├── test_results/                # Generated serial logs & JSON run artifacts
├── wokwi-cli.exe                # Wokwi CLI Windows binary (v0.27.1)
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment configuration template
├── .gitignore                   # Excludes .env, secrets, logs, and binaries
└── README.md
```

---

## ⚙️ Prerequisites & Toolchains

The platform leverages separate toolchains for host validation and embedded cross-compilation:

| Component | Target Role | Local Resolution |
| :--- | :--- | :--- |
| **Python 3.10+** | Test harness, FastAPI, Pydantic, Pytest | System PATH |
| **Host GCC / MinGW** | Native C compilation for host unit tests & logic verification | `gcc` on System PATH |
| **Arduino CLI** | Embedded toolchain manager & compiler | `./bin/arduino-cli.exe` |
| **ESP32 Arduino Core** | Cross-compilation (`xtensa-esp32-elf-gcc`) for ESP32 target | Managed by Arduino CLI |
| **Wokwi CLI** | Headless virtual MCU simulation & serial capture | `./wokwi-cli.exe` |
| **Google Gemini API** | Automated firmware behavioral analysis | Remote REST API |

> [!IMPORTANT]
> **Host Compilation vs Firmware Cross-Compilation**:
> - **Host GCC / MinGW (`gcc`)**: Compiles native C code for execution on the host machine (x86_64). Used for rapid unit testing and host assertions. **Never** used to generate ESP32 firmware binaries.
> - **Arduino CLI + ESP32 Core (`esp32:esp32`)**: Uses the Espressif Xtensa toolchain (`xtensa-esp32-elf-gcc`) to cross-compile firmware into `.bin`/`.elf` binaries formatted specifically for the ESP32 micro-controller architecture to run in Wokwi simulation.

---

## 🔑 Environment Configuration & Secrets

Copy `.env.example` to create your private `.env` file:

```powershell
cp .env.example .env
```

### Configuration Keys & Defaults

| Variable | Default | Description |
| :--- | :--- | :--- |
| `WOKWI_CLI_TOKEN` | *(empty)* | Wokwi CI authentication token. |
| `WOKWI_CLI_PATH` | `./wokwi-cli.exe` | Relative or absolute path to Wokwi CLI binary. |
| `WOKWI_TIMEOUT_MS` | `5000` | Default timeout for simulations in milliseconds. |
| `ARDUINO_CLI_PATH` | `./bin/arduino-cli.exe` | Path to Arduino CLI binary. |
| `ESP32_FQBN` | `esp32:esp32:esp32` | Fully Qualified Board Name for ESP32 target. |
| `ARDUINO_CORE_NAME` | `esp32:esp32` | Core package identifier for ESP32 platform. |
| `GCC_PATH` | `gcc` | Host GCC compiler executable name or path. |
| `GEMINI_API_KEY` | *(empty)* | Google AI Studio API key for Gemini models. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Target Gemini model identifier. |
| `GEMINI_TIMEOUT_SECONDS`| `30.0` | Timeout in seconds for Gemini API calls. |
| `APP_HOST` | `127.0.0.1` | FastAPI server bind address. |
| `APP_PORT` | `8000` | FastAPI server port. |
| `TEST_RESULTS_DIR` | `./test_results` | Directory for saving logs and test artifacts. |
| `DATABASE_URL` | `sqlite:///./firmware_tester.db` | Persistence database connection string. |

### How to Obtain External Service Tokens

1. **Wokwi CI Token**:
   - Go to [https://wokwi.com/dashboard/ci](https://wokwi.com/dashboard/ci).
   - Sign in via GitHub or Google.
   - Click **Get a token** and copy the token (`wok_...`).
   - Paste into `.env`: `WOKWI_CLI_TOKEN=wok_...`.
   - *Note: If no token is provided, the harness automatically falls back to deterministic mock simulation for local development.*

2. **Google Gemini API Key**:
   - Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
   - Click **Create API Key**.
   - Paste into `.env`: `GEMINI_API_KEY=AIzaSy...`.

> [!NOTE]
> **CONFIGURED vs VERIFIED**:
> The system tracks external services using two explicit states:
> - **CONFIGURED**: An API key or token is provided in `.env` / environment.
> - **VERIFIED**: The actual binary or core (e.g. `wokwi-cli.exe`, `arduino-cli.exe`, `esp32:esp32`) is installed and validated to respond on the local machine.

---

## 🛠️ Toolchain Setup Commands

### 1. Python Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Arduino CLI & ESP32 Core Setup
Arduino CLI is pre-bundled in `bin/arduino-cli.exe`. To initialize the index and install the official ESP32 core:
```powershell
# Update core index
.\bin\arduino-cli.exe core update-index --additional-urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json

# Install ESP32 platform core
.\bin\arduino-cli.exe core install esp32:esp32 --additional-urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

---

## 🔍 Verification Commands

Verify all components locally using the following commands:

### Check Toolchain Status
```powershell
# Check Wokwi CLI version
.\wokwi-cli.exe --version

# Check Arduino CLI version
.\bin\arduino-cli.exe version

# Check installed Arduino cores
.\bin\arduino-cli.exe core list

# Check Host GCC compiler
gcc --version
```

### Run Pytest Test Suite
All unit and integration tests run offline without consuming API quotas:
```powershell
# Run all tests
pytest -v

# Run configuration and secret protection tests
pytest -v app/tests/test_config.py

# Run firmware model validation tests
pytest -v app/tests/test_firmware_models.py

# Run deterministic test generator tests
pytest -v app/tests/test_test_generator.py

# Run Gemini analyzer isolation and golden tests
pytest -v app/tests/test_gemini_analyzer.py

# Run pipeline execution tests
pytest -v app/tests/test_pipeline.py
```

---

## 🚀 Running the Web Dashboard & API

Start the FastAPI application:
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

### Key Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Web Dashboard with live health monitors, test runner, and logs |
| `GET` | `/api/health` | System diagnostics (`wokwi`, `gcc`, `arduino_cli`, `esp32_core`, `gemini`) |
| `POST` | `/api/analyze-firmware` | Analyze C firmware using Gemini into structured `FirmwareAnalysis` |
| `POST` | `/api/compile` | Compile C source using Host GCC |
| `POST` | `/api/simulate` | Execute Wokwi CLI simulation and capture serial logs |
| `POST` | `/api/run-test` | Run full test cycle (compile -> simulate -> verify assertions) |
| `GET` | `/api/results` | Fetch historical test run artifacts |

### Diagnostic Health Response (`GET /api/health`)
```json
{
  "status": "OK",
  "wokwi_cli_installed": true,
  "wokwi_cli_path": "D:\\hackathon_project\\firmware-tester\\wokwi-cli.exe",
  "wokwi_token_configured": true,
  "gcc_installed": true,
  "gcc_path": "C:\\Strawberry\\c\\bin\\gcc.EXE",
  "python_version": "3.13.14",
  "arduino_cli_installed": true,
  "arduino_cli_path": "D:\\hackathon_project\\firmware-tester\\bin\\arduino-cli.exe",
  "esp32_core_installed": true,
  "gemini_configured": true,
  "gemini_model": "gemini-2.5-flash"
}
```
