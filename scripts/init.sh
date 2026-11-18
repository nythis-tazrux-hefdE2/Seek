#!/usr/bin/env bash
set -euo pipefail
umask 077
seek_script_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$seek_script_root/scripts/init_project.py" --root "$PWD" "$@"
