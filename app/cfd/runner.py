"""OpenFOAM komutlarını (blockMesh, checkMesh, topoSet, buoyantSimpleFoam)
Ubuntu üzerinde kurulu bir OpenFOAM ortamına karşı çalıştıran yardımcılar.

OpenFOAM kurulu değilse (bu geliştirme/konteyner ortamında olduğu gibi),
fonksiyonlar bunu net bir hata mesajıyla bildirir; case dosyaları yine de
üretilmiş ve incelemeye hazır olur.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandResult:
    command: str
    ok: bool
    output: str


def openfoam_available() -> bool:
    return shutil.which("blockMesh") is not None


def _run(case_dir: Path, cmd: list[str], timeout: int = 1800) -> CommandResult:
    binary = cmd[0]
    if shutil.which(binary) is None:
        return CommandResult(
            command=" ".join(cmd),
            ok=False,
            output=(
                f"'{binary}' bulunamadı. OpenFOAM ortamı bu sistemde kurulu/kaynaklanmış "
                "(sourced) değil. Kurulum için scripts/install_ubuntu.sh dosyasına bakın."
            ),
        )
    try:
        proc = subprocess.run(
            cmd,
            cwd=case_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = proc.stdout[-6000:] + ("\n--- STDERR ---\n" + proc.stderr[-2000:] if proc.stderr else "")
        return CommandResult(command=" ".join(cmd), ok=proc.returncode == 0, output=out)
    except subprocess.TimeoutExpired:
        return CommandResult(command=" ".join(cmd), ok=False, output=f"Zaman aşımı ({timeout}s)")


def run_mesh(case_dir: Path) -> list[CommandResult]:
    results = [_run(case_dir, ["blockMesh"])]
    if results[-1].ok:
        results.append(_run(case_dir, ["checkMesh"]))
    if results[-1].ok and (case_dir / "system" / "topoSetDict").exists():
        results.append(_run(case_dir, ["topoSet"]))
    return results


def run_solver(case_dir: Path, timeout: int = 3600) -> CommandResult:
    return _run(case_dir, ["buoyantSimpleFoam"], timeout=timeout)


def tail_log(case_dir: Path, name: str, n_chars: int = 4000) -> str:
    log_path = case_dir / f"log.{name}"
    if not log_path.exists():
        return ""
    text = log_path.read_text(errors="ignore")
    return text[-n_chars:]
