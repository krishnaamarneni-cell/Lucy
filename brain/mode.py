"""
Lucy's mode switch — the foundation of her safety system.

Lucy has three modes:
  - read: Can only read information. Cannot take any action that changes
          state on the system, in your files, or in the outside world.
          This is the default and safest mode.
  - ask:  Can propose actions but must ask for confirmation before each one.
          The middle ground — Lucy is useful without being scary.
  - edit: Can act without confirmation (within the task you asked for).
          For when you trust her and want speed.

The mode is stored in ~/Lucy/mode.json and can be read by any module.

A hard-deny list blocks dangerous operations regardless of mode. Even in
edit mode, these never happen without explicit override.
"""

import json
import re
from pathlib import Path
from typing import Literal

Mode = Literal["read", "ask", "edit"]
VALID_MODES: tuple[Mode, ...] = ("read", "ask", "edit")

MODE_FILE = Path.home() / "Lucy" / "mode.json"
DEFAULT_MODE: Mode = "read"


# ---------------------------------------------------------------------------
# Hard-deny list — things Lucy should NEVER do, regardless of mode.
# These are patterns that match against a proposed action's description or
# command. If any match, the action is blocked with PermissionError.
# ---------------------------------------------------------------------------

HARD_DENY_PATTERNS = [
    # Destructive shell commands
    r"\brm\s+-rf?\s+/",          # rm -rf / or rm -r / (root deletion)
    r"\brm\s+-rf?\s+~",          # rm -rf ~ (home deletion)
    r"\bmkfs\b",                  # format a filesystem
    r"\bdd\s+if=.*of=/dev/",      # dd writing to a raw device
    r":\(\)\{.*:\|:\&.*\};:",     # fork bomb
    r"\bshutdown\b",              # shutdown
    r"\breboot\b",                # reboot
    r"\bhalt\b",                  # halt
    # Privilege escalation
    r"\bsudo\b",                  # any sudo
    r"\bsu\s+-",                  # su - (become another user)
    r"\bchmod\s+777\b",           # chmod 777 (fully open perms)
    r"\bchmod\s+-R\s+777\b",
    # Financial / payment
    r"\bstripe\b",
    r"\bpaypal\b",
    r"\bvenmo\b",
    r"\bzelle\b",
    r"\btransfer.{0,30}money\b",
    r"\bsend.{0,30}payment\b",
    # Secrets / credentials
    r"\bprivate[_\s-]?key\b",
    r"\bssh[_\s-]?key\b",
    r"\baws[_\s-]?secret\b",
    r"\bapi[_\s-]?key\b(?!.*(example|sample|template))",
    # Editing Lucy's own source code directly (must go through mentor + git branch)
    r"/home/krishna/Lucy/brain/.*\.py",
    r"/home/krishna/Lucy/voice/.*\.py",
    r"/home/krishna/Lucy/main\.py",
]

# Compile once at import time
_DENY_REGEXES = [re.compile(p, re.IGNORECASE) for p in HARD_DENY_PATTERNS]


class PermissionDeniedError(PermissionError):
    """Raised when an action is blocked by mode or by the hard-deny list."""


# ---------------------------------------------------------------------------
# Mode file I/O
# ---------------------------------------------------------------------------

def _read_mode_file() -> Mode:
    """Read the mode from disk. If missing or corrupt, return the default."""
    if not MODE_FILE.exists():
        return DEFAULT_MODE
    try:
        data = json.loads(MODE_FILE.read_text())
        mode = data.get("mode", DEFAULT_MODE)
        if mode not in VALID_MODES:
            return DEFAULT_MODE
        return mode
    except (json.JSONDecodeError, OSError):
        return DEFAULT_MODE


def _write_mode_file(mode: Mode) -> None:
    """Write the mode to disk atomically."""
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode!r}. Must be one of {VALID_MODES}.")
    MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = MODE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"mode": mode}, indent=2) + "\n")
    tmp.replace(MODE_FILE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_mode() -> Mode:
    """Return Lucy's current mode."""
    return _read_mode_file()


def set_mode(mode: Mode) -> Mode:
    """Set Lucy's mode. Returns the new mode. Raises ValueError if invalid."""
    _write_mode_file(mode)
    return mode


def is_read() -> bool:
    return get_mode() == "read"


def is_ask() -> bool:
    return get_mode() == "ask"


def is_edit() -> bool:
    return get_mode() == "edit"


def require_mode(minimum: Mode, *, action_description: str = "") -> None:
    """
    Raise PermissionDeniedError if the current mode is below `minimum`.

    Mode hierarchy (ascending permission):
        read < ask < edit

    Example:
        require_mode("edit", action_description="send email to Sai")
    """
    level = {"read": 0, "ask": 1, "edit": 2}
    current = get_mode()
    if level[current] < level[minimum]:
        raise PermissionDeniedError(
            f"Lucy is in {current!r} mode but this action requires {minimum!r} "
            f"mode or higher. Action: {action_description or '(unspecified)'}"
        )


def check_hard_deny(text: str, *, context: str = "") -> None:
    """
    Check `text` (a command, task description, or proposed action) against the
    hard-deny list. Raises PermissionDeniedError if it matches any pattern.

    This check runs BEFORE the mode check and applies in ALL modes.
    """
    for pattern, regex in zip(HARD_DENY_PATTERNS, _DENY_REGEXES):
        if regex.search(text):
            raise PermissionDeniedError(
                f"Blocked by hard-deny list (pattern: {pattern}). "
                f"Context: {context or '(unspecified)'}"
            )


def check_action(
    action_description: str,
    *,
    minimum_mode: Mode,
    raw_command: str = "",
) -> None:
    """
    The one-stop check for any proposed action.

    Call this BEFORE doing anything that changes state. It:
      1. Runs the hard-deny list against both the description and raw command
      2. Enforces the minimum mode

    Example:
        check_action(
            "send email to Sai",
            minimum_mode="edit",
        )

        check_action(
            "run shell command: rm -rf /tmp/trash",
            minimum_mode="edit",
            raw_command="rm -rf /tmp/trash",
        )
    """
    # Check hard-deny against the description
    check_hard_deny(action_description, context="action description")
    # Check hard-deny against the raw command, if provided
    if raw_command:
        check_hard_deny(raw_command, context="raw command")
    # Now check mode
    require_mode(minimum_mode, action_description=action_description)


# ---------------------------------------------------------------------------
# CLI entry point for `python -m brain.mode <command>`
# ---------------------------------------------------------------------------

def _cli() -> None:
    import sys
    if len(sys.argv) < 2:
        print(f"Lucy mode: {get_mode()}")
        return
    cmd = sys.argv[1].lower()
    if cmd == "status":
        print(f"Lucy mode: {get_mode()}")
    elif cmd in VALID_MODES:
        old = get_mode()
        set_mode(cmd)
        print(f"Lucy mode: {old} -> {cmd}")
    else:
        print(f"Usage: python -m brain.mode [status|read|ask|edit]")
        print(f"Current: {get_mode()}")
        sys.exit(1)


if __name__ == "__main__":
    _cli()
