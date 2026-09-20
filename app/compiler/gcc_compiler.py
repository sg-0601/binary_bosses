import subprocess
import time
import os
from pathlib import Path
from typing import Optional, List
from app.models.schemas import CompilationRequest, CompilationResult
from app.utils.config import settings


class GCCCompiler:
    """Manages building C/C++ firmware and simulation harnesses with GCC/MinGW."""

    def __init__(self, gcc_path: Optional[str] = None):
        self.gcc_path = gcc_path or settings.get_gcc_executable()

    def check_installed(self) -> bool:
        try:
            res = subprocess.run([self.gcc_path, "--version"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False

    def compile(self, request: CompilationRequest) -> CompilationResult:
        src = Path(request.source_file)
        if not src.is_absolute():
            src = (settings.PROJECT_ROOT / src).resolve()

        if not src.exists():
            return CompilationResult(
                success=False,
                stdout="",
                stderr=f"Source file not found: {src}",
                duration_ms=0.0
            )

        if request.output_binary:
            out_bin = Path(request.output_binary)
            if not out_bin.is_absolute():
                out_bin = (settings.PROJECT_ROOT / out_bin).resolve()
        else:
            suffix = ".exe" if os.name == "nt" else ""
            out_bin = src.with_suffix(suffix)

        out_bin.parent.mkdir(parents=True, exist_ok=True)

        cmd = [self.gcc_path, str(src), "-o", str(out_bin), "-Wall", "-O2"]
        if request.compiler_flags:
            cmd.extend(request.compiler_flags)

        start = time.perf_counter()
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            duration = (time.perf_counter() - start) * 1000.0

            return CompilationResult(
                success=(process.returncode == 0),
                output_file=str(out_bin) if process.returncode == 0 else None,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_ms=round(duration, 2)
            )
        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                stdout="",
                stderr="Compilation timed out after 30 seconds",
                duration_ms=30000.0
            )
        except Exception as e:
            return CompilationResult(
                success=False,
                stdout="",
                stderr=str(e),
                duration_ms=0.0
            )


compiler = GCCCompiler()
