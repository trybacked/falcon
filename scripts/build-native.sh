#!/usr/bin/env bash
# Sync dev deps plus the capture backend for the current OS (PyObjC / pywinauto).
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

extra=""
case "$(uname -s)" in
  Darwin) extra=darwin ;;
  MINGW* | MSYS* | CYGWIN* | Windows*) extra=win32 ;;
esac

if [[ -n "$extra" ]]; then
  exec uv sync --extra "$extra" --group dev
fi
exec uv sync --group dev
