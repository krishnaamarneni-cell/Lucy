"""
Lucy's Goose agent bridge.

Goose is a general-purpose AI agent with 70+ MCP extensions.
Lucy delegates tasks that need tool access (GitHub, Gmail, Drive,
browser, databases, file operations) to Goose.
"""

import subprocess
import shutil
import time
import re
import os
from pathlib import Path

GOOSE_BIN = None


def _find_goose() -> str:
    global GOOSE_BIN
    if GOOSE_BIN:
        return GOOSE_BIN
    candidates = [
        shutil.which("goose"),
        str(Path.home() / ".local" / "bin" / "goose"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            GOOSE_BIN = c
            return c
    raise FileNotFoundError("Goose binary not found")


GOOSE_TRIGGERS = [
    "github", "create a pr", "pull request", "create issue", "check my repos",
    "git commit", "git push", "merge branch",
    "gmail", "read my email", "check my email", "send email",
    "google drive", "check my drive", "google doc",
    "google calendar", "my calendar", "schedule",
    "deploy", "vercel", "push to production", "check deployment",
    "supabase", "database", "run query", "check the db",
    "open browser", "browse", "scrape", "fetch this url",
    "go to website", "check this site",
    "create a file", "edit the file", "read the file",
    "write code", "build a script", "make a tool",
    "automate", "run this task", "do this for me",
    "install", "set up", "configure",
    "browse", "visit", "go to", "open this", "read this site",
    "fetch this page", "what's on this site", "check this url",
    ".com", ".org", ".io", ".dev", ".ai",
    "wealthclaude", "north falmouth", "saint francis",
    "hacker news", "hackernews", "nfpltc",
    "lucy repo", "my github",
]

GOOSE_KEYWORD_SETS = {
    "action": {"create", "check", "read", "send", "deploy", "push",
               "build", "write", "edit", "open", "run", "install",
               "set", "configure", "automate", "fetch", "scrape",
               "merge", "commit", "schedule", "browse"},
    "target": {"github", "gmail", "email", "drive", "calendar",
               "vercel", "supabase", "database", "repo", "repos",
               "pr", "issue", "branch", "file", "site", "website",
               "script", "code", "browser", "deployment"},
}


def needs_goose(text: str) -> bool:
    t = text.lower()
    if any(trigger in t for trigger in GOOSE_TRIGGERS):
        return True
    words = set(t.split())
    if words & GOOSE_KEYWORD_SETS["action"] and words & GOOSE_KEYWORD_SETS["target"]:
        return True
    return False


def _try_direct_shell(task: str) -> dict | None:
    """For simple known tasks, run shell commands directly — 100% reliable."""
    t = task.lower()
    cmd = None
    
    if any(w in t for w in ["list all", "all my repo", "my github repo", "github repositories"]):
        cmd = "gh repo list --limit 30"
    elif "git status" in t or ("status" in t and "lucy" in t):
        cmd = "git -C /home/krishna/Lucy status"
    elif "git log" in t or "recent commits" in t or "last commits" in t:
        cmd = "git -C /home/krishna/Lucy log --oneline -10"
    elif "git branch" in t or "my branches" in t:
        cmd = "git -C /home/krishna/Lucy branch -a"
    
    # Browse/fetch URL tasks
    import re as _re
    from brain.browser import resolve_site, summarize_page
    
    # 1. Check known sites first (e.g. "read wealthclaude news")
    known_url = resolve_site(task)
    
    # 2. Check for explicit URLs
    urls = _re.findall(r'https?://[^\s]+', task)
    if not urls:
        domains = _re.findall(r'(?:www\.)?[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?(?:/[^\s]*)?', task)
        if domains:
            urls = [domains[0]]
    
    # 3. Use known site or detected URL
    target_url = known_url or (urls[0] if urls else None)
    if target_url:
        output = summarize_page(target_url, task_hint=task)
        return {"success": True, "output": output, "duration": 0.1}

    if not cmd:
        return None
    
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30,
            env={**os.environ, "PATH": str(Path.home() / ".local" / "bin") + ":" + os.environ.get("PATH", "")},
        )
        output = result.stdout.strip()
        if output:
            return {"success": True, "output": output, "duration": 0.1}
    except Exception:
        pass
    return None


def ask_goose(task: str, timeout: int = 120) -> dict:
    # Try direct shell first for known simple tasks (100% reliable)
    direct = _try_direct_shell(task)
    if direct:
        return direct

    goose_bin = _find_goose()
    task_lower = task.lower()

    hints = ""
    if any(w in task_lower for w in ["github", "repo", "git", "commit", "branch", "push", "repositories"]):
        hints = "Use shell commands like: gh repo list --limit 20 (to list all GitHub repos), git -C /home/krishna/Lucy log --oneline -5, git -C /home/krishna/Lucy remote -v, git -C /home/krishna/Lucy status"
    elif any(w in task_lower for w in ["file", "directory", "folder", "list"]):
        hints = "Use shell commands like: ls, find, cat, head, wc"
    elif any(w in task_lower for w in ["deploy", "vercel"]):
        hints = "Use shell commands like: cd /home/krishna/Lucy/dashboard && npx vercel --prod"
    elif any(w in task_lower for w in ["install", "package", "npm", "pip"]):
        hints = "Use shell commands like: pip install, npm install"

    prompt = (
        f"Execute this shell task. Use the shell tool to run commands directly. "
        f"The user's main project is at /home/krishna/Lucy. "
        f"{hints} "
        f"\n\n"
        f"After running the commands, summarize the results clearly. "
        f"Use markdown formatting: bullet points for lists, bold for emphasis, "
        f"code blocks for command output. Keep it concise but well-structured. "
        f"\n\nTask: {task}"
    )

    env = {**os.environ}
    env["PATH"] = str(Path.home() / ".local" / "bin") + ":" + env.get("PATH", "")

    for attempt in range(2):
        start = time.time()
        try:
            result = subprocess.run(
                [goose_bin, "run", "--text", prompt, "--no-session", "--quiet"],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            duration = time.time() - start
            output = result.stdout.strip()

            if "Failed to call a function" in output or "failed_generation" in output:
                if attempt == 0:
                    print("  ↻ Goose tool call failed, retrying...")
                    continue
                return {
                    "success": False,
                    "output": "Goose had trouble with that task. Try being more specific, like 'run git status in my Lucy project'.",
                    "duration": round(duration, 1),
                }

            if not output and result.stderr:
                if "Failed to call a function" in result.stderr and attempt == 0:
                    print("  ↻ Goose tool call failed, retrying...")
                    continue
                output = f"Goose encountered an issue: {result.stderr[:300]}"

            return {
                "success": result.returncode == 0 and bool(output),
                "output": output or "Goose returned no output.",
                "duration": round(duration, 1),
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": f"Goose timed out after {timeout} seconds.",
                "duration": timeout,
            }
        except FileNotFoundError:
            return {
                "success": False,
                "output": "Goose binary not found.",
                "duration": 0,
            }
        except Exception as e:
            return {
                "success": False,
                "output": f"Goose error: {str(e)}",
                "duration": time.time() - start,
            }

    return {
        "success": False,
        "output": "Goose failed after 2 attempts. Try a more specific request.",
        "duration": 0,
    }


def summarize_for_voice(result: dict) -> str:
    output = result["output"]
    lines = output.split("\n")
    clean = []
    skip = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("─") or stripped.startswith("▸ "):
            skip = True
            continue
        if skip and any(stripped.startswith(p) for p in ["command:", "timeout_secs:", "path:", "depth:"]):
            continue
        skip = False
        if not clean and not stripped:
            continue
        clean.append(line)

    text = "\n".join(clean).strip()

    # Detect if this is gh repo list output
    is_repo_list = "public" in text and "/" in text and text.count("/") >= 3
    
    formatted = []
    repo_count = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Detect repo lines: starts with username/repo pattern
        if is_repo_list and "/" in stripped and stripped[0].isalpha():
            parts = stripped.split()
            if len(parts) >= 2:
                repo_name = parts[0]
                short_name = repo_name.split("/")[-1]
                # Find visibility and date
                visibility = ""
                desc_parts = []
                for p in parts[1:]:
                    if p in ("public", "private", "public,", "private,"):
                        visibility = p.rstrip(",")
                    elif p in ("fork", "fork,"):
                        visibility += ", fork" if visibility else "fork"
                    elif re.match(r"20\d{2}-", p):
                        pass  # skip date
                    else:
                        desc_parts.append(p)
                desc = " ".join(desc_parts).strip()
                entry = f"- **{short_name}**"
                if desc:
                    entry += f" — {desc}"
                if visibility:
                    entry += f" *({visibility})*"
                formatted.append(entry)
                repo_count += 1
                continue

        # Detect git log lines: short hash (hex only) + message
        if len(stripped) >= 8 and all(c in "0123456789abcdef" for c in stripped[:7]) and " " in stripped[7:10]:
            h = stripped[:7]
            msg = stripped[8:].strip()
            formatted.append(f"- `{h}` {msg}")
            continue

        # Regular text — keep as-is
        formatted.append(stripped)

    if repo_count > 0:
        formatted.append(f"\n**{repo_count} repositories total**")

    result_text = "\n".join(formatted).strip()
    return result_text if result_text else text
