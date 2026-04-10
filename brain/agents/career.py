"""
Lucy's career specialist agent.

Delegates job search tasks to the career-ops system via Claude Code.
Career-ops runs as a Claude Code skill — Lucy sends a task description,
Claude Code reads the career-ops CLAUDE.md and mode files, and executes
the requested operation (scan, evaluate, generate PDF, etc.).

Usage from Lucy's brain:
    from brain.agents.career import ask_career
    result = ask_career("evaluate this job: https://example.com/job/123")
    result = ask_career("scan for new SAP MM roles")
    result = ask_career("generate a tailored resume for this JD: ...")
"""

import subprocess
import shutil
import time
from pathlib import Path

CAREER_OPS_DIR = Path.home() / "career-ops"
CLAUDE_BIN = None


def _find_claude() -> str:
    """Find the Claude Code CLI binary."""
    global CLAUDE_BIN
    if CLAUDE_BIN:
        return CLAUDE_BIN

    candidates = [
        shutil.which("claude"),
        str(Path.home() / ".local" / "bin" / "claude"),
        "/usr/local/bin/claude",
    ]
    for c in candidates:
        if c and Path(c).exists():
            CLAUDE_BIN = c
            return c
    raise FileNotFoundError("Claude Code CLI not found")


# Career task detection keywords
CAREER_TRIGGERS = [
    "find me jobs", "find jobs", "search jobs", "job search",
    "find me roles", "search for roles", "find roles",
    "sap jobs", "sap roles", "sap contract",
    "scan for jobs", "scan portals", "scan careers",
    "evaluate this job", "evaluate this role", "evaluate this offer",
    "generate resume", "generate cv", "tailor resume", "tailor cv",
    "create resume", "create cv", "make resume",
    "job at", "role at", "position at",
    "career search", "career scan",
    "how's my job search", "job tracker", "application tracker",
    "linkedin outreach", "outreach message",
    "company research", "deep research",
]

CAREER_TASK_MAP = {
    "scan": ["scan for jobs", "scan portals", "scan careers", "find me jobs",
             "find jobs", "search jobs", "job search", "find me roles",
             "search for roles", "find roles", "sap jobs", "sap roles",
             "sap contract"],
    "evaluate": ["evaluate this job", "evaluate this role", "evaluate this offer",
                 "job at", "role at", "position at"],
    "pdf": ["generate resume", "generate cv", "tailor resume", "tailor cv",
            "create resume", "create cv", "make resume"],
    "tracker": ["how's my job search", "job tracker", "application tracker"],
    "contacto": ["linkedin outreach", "outreach message"],
    "deep": ["company research", "deep research"],
}



def _load_cv_summary() -> str:
    """Load a summary of the user's CV for quick Groq-based answers."""
    cv_path = CAREER_OPS_DIR / "cv.md"
    profile_path = CAREER_OPS_DIR / "config" / "profile.yml"
    summary_parts = []
    try:
        if cv_path.exists():
            cv_text = cv_path.read_text()[:2000]  # first 2000 chars
            summary_parts.append(cv_text)
    except Exception:
        pass
    try:
        if profile_path.exists():
            profile_text = profile_path.read_text()[:1000]
            summary_parts.append(profile_text)
    except Exception:
        pass
    return "\n---\n".join(summary_parts) if summary_parts else ""


# Tasks that NEED Claude Code (heavy, complex, file generation)
HEAVY_CAREER_TASKS = [
    "generate resume", "generate cv", "tailor resume", "tailor cv",
    "create resume", "create cv", "make resume", "make cv",
    "evaluate this job", "evaluate this role", "evaluate this offer",
    "scan portals", "scan for jobs", "scan careers",
    "batch", "pipeline",
    "apply to", "fill application",
    "linkedin outreach", "outreach message",
]


def is_heavy_career_task(text: str) -> bool:
    """Check if this career task needs Claude Code (heavy) or can use Groq (fast)."""
    t = text.lower()
    return any(trigger in t for trigger in HEAVY_CAREER_TASKS)


def ask_career_fast(task: str) -> str:
    """
    Fast career Q&A using Lucy's normal Groq brain.
    Loads the user's CV and profile, passes them as context to LLaMA.
    Returns in ~1-2 seconds instead of 30+.
    """
    cv_summary = _load_cv_summary()
    if not cv_summary:
        return "I couldn't load your career profile. Make sure cv.md exists in the career-ops folder."

    import os
    from groq import Groq
    from dotenv import load_dotenv
    load_dotenv()
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    messages = [
        {
            "role": "system",
            "content": (
                "You are a career advisor for Krishna, an SAP functional consultant. "
                "Here is his CV and profile:\n\n"
                f"{cv_summary}\n\n"
                "Answer career questions based on this profile. "
                "Be specific about his SAP skills (MM, SD, Ariba, master data, S/4HANA). "
                "Keep responses to 2-4 sentences. Plain conversational text only."
            ),
        },
        {"role": "user", "content": task},
    ]

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Career advice error: {str(e)}"


def needs_career(text: str) -> bool:
    """Check if the user's message is a career/job search task."""
    t = text.lower()

    # First check exact substring matches
    if any(trigger in t for trigger in CAREER_TRIGGERS):
        return True

    # Keyword-based detection: if the message contains job-related
    # words in combination, it's a career task
    job_words = {"job", "jobs", "role", "roles", "position", "positions",
                 "career", "careers", "hiring", "openings", "vacancy",
                 "vacancies", "contract", "consultant", "employment"}
    action_words = {"find", "search", "look", "scan", "get", "show",
                    "list", "any", "browse", "hunt"}
    resume_words = {"resume", "cv", "cover letter", "application",
                    "tailor", "apply", "applying"}

    words = set(t.split())

    # Job search: has a job word AND an action word
    if words & job_words and words & action_words:
        return True

    # Resume/CV work: has a resume word
    if words & resume_words:
        return True

    # SAP + job context
    if "sap" in t and words & job_words:
        return True

    return False


def _detect_mode(text: str) -> str:
    """Detect which career-ops mode to use based on the user's message."""
    t = text.lower()
    for mode, triggers in CAREER_TASK_MAP.items():
        if any(trig in t for trig in triggers):
            return mode
    return "scan"


def ask_career(task: str, timeout: int = 300) -> dict:
    """
    Send a career task to Claude Code with career-ops context.

    Returns a dict with:
        success: bool
        output: str (the result text)
        mode: str (which career-ops mode was used)
        duration: float (seconds)
    """
    claude_bin = _find_claude()
    mode = _detect_mode(task)

    prompt = (
        f"Read the user profile at config/profile.yml and CV at cv.md. "
        f"The user is Krishna, an SAP functional consultant specializing in "
        f"MM, SD, Ariba, and master data. "
        f"\n\n"
        f"Based on the request below, help with the career task. "
        f"If asked to find or search for jobs, use web search to find "
        f"real current job listings matching the user profile. "
        f"If asked to evaluate a job, read the job description and score it. "
        f"If asked to generate a resume or CV, read cv.md and tailor it. "
        f"\n\n"
        f"IMPORTANT: Respond in plain conversational text suitable for "
        f"a voice assistant to speak aloud. No markdown, no tables, no "
        f"bullet points, no code blocks. Keep it concise — 3-5 sentences. "
        f"\n\n"
        f"User request: {task}"
    )

    start = time.time()
    try:
        result = subprocess.run(
            [claude_bin, "-p", prompt, "--allowedTools", "WebSearch,WebFetch,Read,Write,Bash"],
            cwd=str(CAREER_OPS_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.time() - start
        output = result.stdout.strip()

        if not output and result.stderr:
            output = f"Career agent encountered an issue: {result.stderr[:200]}"

        return {
            "success": result.returncode == 0 and bool(output),
            "output": output or "No results returned from career search.",
            "mode": mode,
            "duration": round(duration, 1),
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": f"Career search timed out after {timeout} seconds. The task may be too complex for a single query.",
            "mode": mode,
            "duration": timeout,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "output": "Claude Code CLI not found. Career agent needs Claude Code installed.",
            "mode": mode,
            "duration": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "output": f"Career agent error: {str(e)}",
            "mode": mode,
            "duration": time.time() - start,
        }


def summarize_for_voice(result: dict) -> str:
    """Convert a career agent result to voice-friendly text."""
    if not result["success"]:
        return result["output"]

    output = result["output"]

    # Strip any markdown that Claude Code might have included
    import re
    output = re.sub(r"```[\s\S]*?```", "", output)
    output = re.sub(r"\|.*\|", "", output)
    output = re.sub(r"#{1,6}\s+", "", output)
    output = re.sub(r"\*\*([^*]+)\*\*", r"\1", output)
    output = re.sub(r"\*([^*]+)\*", r"\1", output)
    output = re.sub(r"^[-*]\s+", "", output, flags=re.MULTILINE)
    output = re.sub(r"\n{3,}", "\n\n", output)

    return output.strip()
