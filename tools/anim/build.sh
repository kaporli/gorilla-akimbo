#!/bin/bash
# Entry point of the animation build: see build.py (usage) and README.md in this folder.
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python "$HERE/build.py" "$@"
