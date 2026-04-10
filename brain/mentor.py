"""
Lucy's mentor bridge to Claude Code.

Philosophy: Claude Code is Lucy's senior mentor. When Lucy doesn't know
how to do something, she asks her mentor. Every interaction is logged
so Lucy can learn from what she observes.

Lucy stays independent — the mentor is a tool she reaches for, not a
dependency. Native capabilities are always preferred.
"""

import os
import shutil
import re
import subprocess
import tempfile
import time
from pathlib import Path

# Resolve claude binary once at import time.
def _find_claude():
    found = shutil.which("claude")
    if found:
        return found
    candidates = [
        Path.home() / ".local" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
        Path("/usr/bin/claude"),
    ]
    for c in candidates:
        if c.exists() and os.access(c, os.X_OK):
            return str(c)
    return "claude"

CLAUDE_BIN = _find_claude()



VOICE_MODE_INSTRUCTIONS = (
    "You are answering a spoken voice question. Respond in 1-3 short, natural sentences. "
    "Plain speech only. No markdown, no code blocks, no tables, no bullet points, no headers. "
    "If you would normally use an example, describe it in words instead. "
    "Here is the question: "
)


DESIGN_DIR = Path.home() / "Lucy" / "designs" / "awesome-design-md" / "design-md"

# Keywords that suggest the user wants to build UI/website
_UI_KEYWORDS = [
    "website", "landing page", "web page", "webpage", "frontend",
    "component", "ui", "dashboard", "layout", "design",
    "build a page", "build a site", "create a page", "create a site",
    "next.js", "react", "tailwind", "html", "css",
]

def _find_design_file(task: str) -> str:
    """Find a matching design system file based on the task."""
    if not DESIGN_DIR.exists():
        return ""
    t = task.lower()
    # Check if any brand is mentioned
    try:
        for brand_dir in DESIGN_DIR.iterdir():
            if brand_dir.is_dir() and brand_dir.name.lower() in t:
                for fname in ["DESIGN.md", "README.md"]:
                    md = brand_dir / fname
                    if md.exists():
                        return md.read_text()[:3000]
    except Exception:
        pass
    return ""

def _get_design_context(task: str) -> str:
    """Build design context string if the task involves UI/website building."""
    t = task.lower()
    if not any(kw in t for kw in _UI_KEYWORDS):
        return ""
    
    # Try to find a specific brand match
    specific = _find_design_file(task)
    if specific:
        return (
            "\n\nDESIGN SYSTEM: A design system file was found matching this request. "
            "Follow these design guidelines for colors, fonts, spacing, and components:\n"
            f"{specific}\n"
        )
    
    # No specific brand — list available options
    try:
        available = [d.name for d in DESIGN_DIR.iterdir() if d.is_dir()]
        brands = ", ".join(sorted(available)[:20])
        return (
            f"\n\nDESIGN SYSTEMS AVAILABLE: The following brand design systems are at "
            f"{DESIGN_DIR}/. You can read any DESIGN.md file for styling guidance: {brands}. "
            f"Pick the most appropriate one for the request, or use a clean modern style."
        )
    except Exception:
        return ""

def wrap_for_voice(task: str) -> str:
    """Prepend voice-mode instructions so Claude Code formats for speech."""
    return VOICE_MODE_INSTRUCTIONS + task

def ask_mentor(task: str, workspace: str = None, timeout: int = 300, voice_mode: bool = True) -> dict:
    """
    Ask Claude Code to do something.

    Args:
        task: The request, in plain English.
        workspace: Directory where Claude Code works. If None, uses a
                   fresh temp directory (safe — can't touch Lucy's code).
                   Pass an absolute path to let Claude Code work there.
        timeout: Max seconds to wait. Default 5 minutes.

    Returns:
        A dict with task, workspace, output, error, success, duration_s.
    """
    if workspace is None:
        workspace = tempfile.mkdtemp(prefix="lucy-mentor-")
    else:
        Path(workspace).mkdir(parents=True, exist_ok=True)

    start = time.time()
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "-p", (wrap_for_voice(task) if voice_mode else task) + _get_design_context(task)],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = round(time.time() - start, 1)
        return {
            "task": task,
            "workspace": workspace,
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
            "success": result.returncode == 0,
            "duration_s": duration,
        }
    except subprocess.TimeoutExpired:
        return {
            "task": task,
            "workspace": workspace,
            "output": "",
            "error": f"Mentor timed out after {timeout}s",
            "success": False,
            "duration_s": timeout,
        }
    except FileNotFoundError:
        return {
            "task": task,
            "workspace": workspace,
            "output": "",
            "error": "Claude Code not found. Is 'claude' in PATH?",
            "success": False,
            "duration_s": 0,
        }


def _strip_markdown(text: str) -> str:
    """Remove markdown characters that sound awful when read aloud."""
    import re
    # Drop entire markdown table blocks (lines containing pipes with dashes)
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip table separator rows like |---|---|
        if re.match(r"^\|?[\s\-:|]+\|?$", stripped) and "-" in stripped:
            continue
        # Skip pure table rows (starts with | or contains multiple |)
        if stripped.startswith("|") or stripped.count("|") >= 2:
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    # Code fences and inline code
    text = re.sub(r"```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    # Bold/italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    # Headers
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # Bullet markers at line start
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    # Stray pipe characters
    text = text.replace("|", " ")
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def summarize_for_voice(result: dict, max_chars: int = 400) -> str:
    """
    Turn a mentor result into something Lucy can say out loud.
    Strips markdown, flattens to plain speech, trims to voice-friendly length.
    """
    if not result["success"]:
        return f"Sorry, I ran into a problem asking Claude Code: {result['error'][:150]}"

    output = result["output"]
    if not output:
        return "Claude Code finished but didn't return anything."

    # Strip markdown noise
    clean = _strip_markdown(output)

    # Flatten multi-paragraph to single line for voice
    clean = " ".join(p.strip() for p in clean.split("\n\n") if p.strip())
    clean = re.sub(r"\s+", " ", clean)

    # Trim to voice-friendly length on a sentence or word boundary
    if len(clean) > max_chars:
        trimmed = clean[:max_chars]
        # Try to end on a sentence
        last_period = trimmed.rfind(". ")
        if last_period > max_chars * 0.6:
            clean = trimmed[: last_period + 1]
        else:
            clean = trimmed.rsplit(" ", 1)[0] + "..."

    return clean
