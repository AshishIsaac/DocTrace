#!/usr/bin/env bash
# One-time setup for macOS / Linux. Finds Python 3.10+ and runs scripts/bootstrap.py
# Options: --yes (install all extras)  --no-extras  --cpu  --gpu  --gdrive
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for c in ${PYTHON:-} python3.12 python3.13 python3.11 python3.10 python3 python; do
  if command -v "$c" >/dev/null 2>&1 &&
     "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$c"
    break
  fi
done

if [ -z "$PY" ]; then
  echo "Python 3.10 or newer was not found."
  case "$(uname -s)" in
    Darwin) echo "Install it with:  brew install python@3.12   (or from https://www.python.org)" ;;
    *)      echo "Install it with:  sudo apt install python3 python3-venv   (or your distro's equivalent)" ;;
  esac
  exit 1
fi

if ! "$PY" -c 'import venv, ensurepip' 2>/dev/null; then
  echo "$PY is missing the venv module. On Debian/Ubuntu run:  sudo apt install python3-venv"
  exit 1
fi

exec "$PY" scripts/bootstrap.py "$@"
