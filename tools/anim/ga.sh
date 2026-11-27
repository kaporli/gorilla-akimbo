#!/bin/bash
# Entry point of the gun and animation pipeline commands: see ga.py (usage) and README.md in this folder.
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python "$HERE/ga.py" "$@"
