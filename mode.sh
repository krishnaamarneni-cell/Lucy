#!/usr/bin/env bash
# Quick mode toggle for Lucy
# Usage:
#   ~/Lucy/mode.sh           -> show current mode
#   ~/Lucy/mode.sh status    -> show current mode
#   ~/Lucy/mode.sh read      -> switch to read-only
#   ~/Lucy/mode.sh ask       -> switch to ask-before-acting
#   ~/Lucy/mode.sh edit      -> switch to act-directly

LUCY_DIR="$HOME/Lucy"
cd "$LUCY_DIR" || { echo "Lucy dir not found: $LUCY_DIR"; exit 1; }

# Use the venv Python so imports work
PYTHON="$LUCY_DIR/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON="python3"
fi

"$PYTHON" -m brain.mode "${1:-status}"
