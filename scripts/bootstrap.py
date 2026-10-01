"""One-time setup, called by setup.bat / setup.sh (runs with any Python 3.10+).

    python scripts/bootstrap.py [--yes] [--no-extras] [--cpu] [--gpu] [--gdrive]

1. creates the .venv virtual environment
2. installs PyTorch (CUDA build if an NVIDIA GPU is found and you agree, otherwise the small CPU build)
3. installs requirements.txt
4. creates .env and data/
5. offers to install Tesseract (OCR) and Ollama (AI answers) if they are missing
6. downloads the embedding model and runs doctor.py
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"
VPY = VENV / ("Scripts/python.exe" if WIN else "bin/python")
TORCH_CPU = "https://download.pytorch.org/whl/cpu"
TORCH_CUDA = "https://download.pytorch.org/whl/cu126"


def step(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def run(cmd: list[str], check: bool = True) -> bool:
    print("   $ " + " ".join(str(c) for c in cmd), flush=True)
    ok = subprocess.run([str(c) for c in cmd], cwd=ROOT).returncode == 0
    if check and not ok:
        sys.exit(f"\nSetup failed at: {' '.join(str(c) for c in cmd)}")
    return ok


def works(cmd: list[str]) -> bool:
    try:
        return subprocess.run([str(c) for c in cmd], cwd=ROOT, capture_output=True).returncode == 0
    except OSError:
        return False


def ask(question: str, args) -> bool:
    if args.yes:
        return True
    if args.no_extras or not sys.stdin.isatty():
        return False
    try:
        return input(f"   {question} [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def pip(*packages: str, check: bool = True) -> bool:
    cmd = [VPY, "-m", "pip", "install", "--disable-pip-version-check", *packages]
    if run(cmd, check=False):
        return True
    # usually a file briefly locked by antivirus on Windows, or a dropped connection
    print("   retrying once ...")
    time.sleep(5)
    return run(cmd, check=check)


# ------------------------------------------------------------------ steps
def make_venv() -> None:
    step("Creating virtual environment (.venv)")
    if VPY.exists() and works([VPY, "-c", "import sys"]):
        print("   already exists")
        return
    if VENV.exists():
        shutil.rmtree(VENV)  # broken venv (e.g. Python was upgraded) - recreate it
    venv.create(VENV, with_pip=True)
    run([VPY, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])


def install_torch(args) -> None:
    step("Installing PyTorch")
    if works([VPY, "-c", "import torch"]):
        print("   already installed")
        return
    if MAC:
        pip("torch")  # includes Apple GPU (MPS) support
        return
    gpu = not args.cpu and shutil.which("nvidia-smi") and works(["nvidia-smi"])
    if gpu and (args.gpu or ask(
            "NVIDIA GPU found. Install the GPU build of PyTorch (~2.5 GB download, faster indexing)?\n"
            "   Otherwise the CPU build (~200 MB) is used, which is fine for most collections.", args)):
        if pip("torch", "--index-url", TORCH_CUDA, check=False):
            return
        print("   GPU build failed; falling back to the CPU build")
    else:
        print("   installing the CPU build (small download)")
    pip("torch", "--index-url", TORCH_CPU)


def install_requirements(args) -> None:
    step("Installing Python packages")
    pip("-r", "requirements.txt")
    if args.gdrive:
        pip("-r", "requirements-gdrive.txt")


def make_files() -> None:
    step("Creating .env and data/")
    env = ROOT / ".env"
    if not env.exists():
        shutil.copy(ROOT / ".env.example", env)
        print("   created .env (edit it to change settings)")
    (ROOT / "data").mkdir(exist_ok=True)


def have_tesseract() -> bool:
    if shutil.which("tesseract"):
        return True
    return WIN and any(Path(p).exists() for p in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ))


def have_ollama() -> bool:
    if shutil.which("ollama"):
        return True
    if WIN:
        return (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe").exists()
    return MAC and Path("/Applications/Ollama.app").exists()


def system_install(winget_id: str, brew: list[str], linux: str) -> bool:
    if WIN:
        if not shutil.which("winget"):
            print("   winget is not available; install it manually (see README)")
            return False
        return run(["winget", "install", "-e", "--id", winget_id,
                    "--accept-source-agreements", "--accept-package-agreements"], check=False)
    if MAC:
        if not shutil.which("brew"):
            print("   Homebrew is not installed; see https://brew.sh or the README")
            return False
        return run(["brew", "install", *brew], check=False)
    return run(["sh", "-c", linux], check=False)


def extras(args) -> None:
    step("Optional extras")
    if have_tesseract():
        print("   Tesseract OCR: installed")
    elif ask("Install Tesseract OCR (reads images and scanned PDFs)?", args):
        system_install("UB-Mannheim.TesseractOCR", ["tesseract"],
                       "sudo apt-get install -y tesseract-ocr || sudo dnf install -y tesseract")
    else:
        print("   Tesseract OCR: skipped (images / scanned PDFs won't be searchable)")

    if have_ollama():
        print("   Ollama: installed")
    elif ask("Install Ollama (writes answers from your files; needs ~2 GB for a model)?", args):
        system_install("Ollama.Ollama", ["--cask", "ollama"], "curl -fsSL https://ollama.com/install.sh | sh")
    else:
        print("   Ollama: skipped (search works; no AI-written answers)")

    if have_ollama() and ask("Download the Ollama model now (about 2 GB)?", args):
        run([VPY, "doctor.py", "--pull-ollama-model"], check=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", "-y", action="store_true", help="answer yes to every optional install")
    ap.add_argument("--no-extras", action="store_true", help="don't offer Tesseract / Ollama")
    ap.add_argument("--cpu", action="store_true", help="install CPU-only PyTorch even with a GPU")
    ap.add_argument("--gpu", action="store_true", help="install CUDA PyTorch if an NVIDIA GPU is found")
    ap.add_argument("--gdrive", action="store_true", help="also install Google Drive support")
    args = ap.parse_args()

    if sys.version_info < (3, 10):  # noqa: UP036 - may run under any system Python
        sys.exit(f"Python 3.10+ is required (this is {sys.version.split()[0]}).")
    if sys.version_info >= (3, 14):
        print("Note: Python 3.14+ is very new; if a package fails to install, use Python 3.12.")

    make_venv()
    install_torch(args)
    install_requirements(args)
    make_files()
    extras(args)

    step("Downloading the embedding model and checking the setup")
    run([VPY, "doctor.py", "--download-model"], check=False)
    # start.bat / start.sh re-run setup until this marker exists (e.g. after an interrupted install)
    (VENV / ".setup-complete").write_text("ok\n")

    activate = r".venv\Scripts\activate" if WIN else "source .venv/bin/activate"
    start = "start.bat" if WIN else "bash start.sh"
    print(f"""
Setup complete.

  1. Put your files in:  {ROOT / 'data'}   (or set DOCTRACE_DATA_DIR in .env)
  2. Run:                {start}

(or manually: {activate} ; python ingest.py ; python search_app.py)
""")


if __name__ == "__main__":
    main()
