"""
Lucy's deployer.
Deploys projects from ~/Lucy/mentor_workspace/ to GitHub and Vercel.
"""

import os
import re
import subprocess
from pathlib import Path
from datetime import datetime

WORKSPACE_DIR = Path.home() / "Lucy" / "mentor_workspace"


DEPLOY_TRIGGERS = [
    "deploy", "deploy to github", "deploy to vercel",
    "push to github", "publish site", "make it live",
    "go live", "push this", "deploy this",
]


def needs_deployer(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in DEPLOY_TRIGGERS)


def _run(cmd: str, cwd: str = None, timeout: int = 300) -> tuple:
    """Run shell command, return (success, output)."""
    try:
        env = {**os.environ}
        env["PATH"] = f"{Path.home()}/.nvm/versions/node/v20.20.2/bin:{Path.home()}/.local/bin:" + env.get("PATH", "")
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True,
            text=True, timeout=timeout, env=env,
        )
        return (result.returncode == 0, result.stdout + result.stderr)
    except Exception as e:
        return (False, str(e))


def find_latest_project() -> Path | None:
    """Find the most recently created mentor workspace with files."""
    if not WORKSPACE_DIR.exists():
        return None
    dirs = []
    for d in WORKSPACE_DIR.iterdir():
        if d.is_dir():
            files = list(d.glob("*"))
            if files:  # only non-empty folders
                dirs.append((d, d.stat().st_mtime))
    if not dirs:
        return None
    dirs.sort(key=lambda x: x[1], reverse=True)
    return dirs[0][0]


def find_project(name: str) -> Path | None:
    """Find a specific project by name."""
    if not WORKSPACE_DIR.exists():
        return None
    # Exact match
    path = WORKSPACE_DIR / name
    if path.exists():
        return path
    # Fuzzy match
    for d in WORKSPACE_DIR.iterdir():
        if d.is_dir() and name.lower() in d.name.lower():
            return d
    return None


def deploy_to_github(project_path: Path, repo_name: str) -> dict:
    """Initialize git, commit, and push to a new GitHub repo."""
    result = {"success": False, "url": "", "log": []}

    # 1. Init git if needed
    if not (project_path / ".git").exists():
        ok, out = _run("git init", cwd=str(project_path))
        result["log"].append(f"{'✅' if ok else '❌'} git init")
        if not ok:
            result["log"].append(out[:200])
            return result

    # 2. Create README if missing
    readme = project_path / "README.md"
    if not readme.exists():
        readme.write_text(f"# {repo_name}\n\nBuilt by Lucy 🤖 on {datetime.now().strftime('%Y-%m-%d')}\n")

    # 3. Add + commit
    _run("git add .", cwd=str(project_path))
    ok, out = _run('git commit -m "Initial commit via Lucy"', cwd=str(project_path))
    result["log"].append(f"{'✅' if ok else '⚠️'} git commit")

    # 4. Check if repo exists on GitHub already
    ok_check, _ = _run(f"gh repo view {repo_name}", cwd=str(project_path))

    if ok_check:
        # Repo exists — push to it
        _run("git remote remove origin", cwd=str(project_path))
        ok_get, user_out = _run("gh api user -q .login", cwd=str(project_path))
        user = user_out.strip() if ok_get else "krishnaamarneni-cell"
        _run(f"git remote add origin https://github.com/{user}/{repo_name}.git", cwd=str(project_path))
        ok_push, out_push = _run("git branch -M main && git push -u origin main --force", cwd=str(project_path))
        result["log"].append(f"{'✅' if ok_push else '❌'} git push to existing repo")
    else:
        # Create new repo and push
        ok_create, out_create = _run(
            f"gh repo create {repo_name} --public --source=. --remote=origin --push",
            cwd=str(project_path),
        )
        result["log"].append(f"{'✅' if ok_create else '❌'} gh repo create")
        if not ok_create:
            result["log"].append(out_create[:300])
            return result

    # 5. Get the URL
    ok_url, url_out = _run("gh repo view --json url -q .url", cwd=str(project_path))
    if ok_url:
        result["url"] = url_out.strip()
        result["success"] = True

    return result


def deploy_to_vercel(project_path: Path) -> dict:
    """Deploy to Vercel."""
    result = {"success": False, "url": "", "log": []}

    ok, out = _run("/home/krishna/.nvm/versions/node/v20.20.2/bin/vercel --prod --yes", cwd=str(project_path), timeout=600)
    result["log"].append(f"{'✅' if ok else '❌'} vercel --prod")

    # Extract the deployment URL
    url_match = re.search(r'https://[a-zA-Z0-9-]+\.vercel\.app', out)
    if url_match:
        result["url"] = url_match.group(0)
        result["success"] = True
    else:
        result["log"].append(out[-400:])

    return result


def handle_deployer(text: str) -> str:
    t = text.lower()

    # Determine which project to deploy
    project = None
    name_match = re.search(r'(?:project|called|named)\s+([a-z][\w-]*)', t)
    if name_match:
        project = find_project(name_match.group(1))
    
    if not project:
        project = find_latest_project()

    if not project:
        return "No project found in `~/Lucy/mentor_workspace/`. Build something first with the mentor."

    # Generate a repo name from the folder
    repo_name = project.name.replace("task-", "lucy-site-")

    output = [f"📦 **Deploying {project.name}**\n"]
    output.append(f"Location: `{project}`\n")

    deploy_github = "github" in t or ("vercel" not in t and "deploy" in t)
    deploy_vercel = "vercel" in t or ("github" not in t and "deploy" in t)

    # If just "deploy", do both
    if "deploy" in t and "github" not in t and "vercel" not in t:
        deploy_github = True
        deploy_vercel = True

    if deploy_github:
        output.append("\n### GitHub")
        gh_result = deploy_to_github(project, repo_name)
        for line in gh_result["log"]:
            output.append(f"- {line}")
        if gh_result["url"]:
            output.append(f"\n🔗 **Repo:** {gh_result['url']}")

    if deploy_vercel:
        output.append("\n### Vercel")
        v_result = deploy_to_vercel(project)
        for line in v_result["log"]:
            output.append(f"- {line}")
        if v_result["url"]:
            output.append(f"\n🚀 **Live:** {v_result['url']}")

    return "\n".join(output)
