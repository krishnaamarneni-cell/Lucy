"""
Lucy's Skill Workshop — builds new skills via Claude Code mentor with human approval.
Each skill is a standalone Python module in brain/skills/_approved/ after review.
"""

import re
import json
import subprocess
from pathlib import Path
from datetime import datetime

SKILLS_DIR = Path.home() / "Lucy" / "brain" / "skills"
PENDING_DIR = SKILLS_DIR / "_pending"
APPROVED_DIR = SKILLS_DIR / "_approved"
REJECTED_DIR = SKILLS_DIR / "_rejected"

SKILL_CATALOG = {
    "alpha_vantage": {
        "description": "Real-time stock prices and financial data via Alpha Vantage API",
        "api_url": "https://www.alphavantage.co/documentation/",
        "env_keys": ["ALPHA_VANTAGE_KEY"],
        "example_endpoint": "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=IBM&apikey=demo",
        "sample_usage": "get_stock_price('TSLA')",
    },
    "github_trending": {
        "description": "Trending repos on GitHub by language/timeframe",
        "api_url": "https://docs.github.com/en/rest/search",
        "env_keys": [],
        "example_endpoint": "https://api.github.com/search/repositories?q=stars:>1000&sort=stars&order=desc",
        "sample_usage": "get_trending_repos('python', 'daily')",
    },
    "hackernews_top": {
        "description": "Top stories from HackerNews",
        "api_url": "https://github.com/HackerNews/API",
        "env_keys": [],
        "example_endpoint": "https://hacker-news.firebaseio.com/v0/topstories.json",
        "sample_usage": "get_top_hn_stories(10)",
    },
    "reddit_top": {
        "description": "Top posts from a subreddit",
        "api_url": "https://www.reddit.com/dev/api",
        "env_keys": [],
        "example_endpoint": "https://www.reddit.com/r/SAP/top.json?limit=10",
        "sample_usage": "get_reddit_top('SAP', 10)",
    },
    "exchange_rates": {
        "description": "Currency exchange rates (free, no auth)",
        "api_url": "https://www.exchangerate-api.com/docs/free",
        "env_keys": [],
        "example_endpoint": "https://open.er-api.com/v6/latest/USD",
        "sample_usage": "convert_currency(100, 'USD', 'EUR')",
    },
    "adzuna_jobs": {
        "description": "Adzuna job search API for US SAP jobs",
        "api_url": "https://developer.adzuna.com/",
        "env_keys": ["ADZUNA_APP_ID", "ADZUNA_APP_KEY"],
        "example_endpoint": "https://api.adzuna.com/v1/api/jobs/us/search/1?app_id=X&app_key=Y&what=sap",
        "sample_usage": "search_adzuna_jobs('sap consultant')",
    },
    "usajobs": {
        "description": "US federal government jobs via USAJobs.gov",
        "api_url": "https://developer.usajobs.gov/",
        "env_keys": ["USAJOBS_EMAIL", "USAJOBS_KEY"],
        "example_endpoint": "https://data.usajobs.gov/api/search?Keyword=SAP",
        "sample_usage": "search_usajobs('SAP')",
    },
    "quotable": {
        "description": "Random inspirational quotes for morning briefing",
        "api_url": "https://github.com/lukePeavey/quotable",
        "env_keys": [],
        "example_endpoint": "https://api.quotable.io/random",
        "sample_usage": "get_random_quote()",
    },
    "weather_openmeteo": {
        "description": "Free weather API with no auth (better than wttr.in, proper encoding)",
        "api_url": "https://open-meteo.com/en/docs",
        "env_keys": [],
        "example_endpoint": "https://api.open-meteo.com/v1/forecast?latitude=40.7&longitude=-74.0&current=temperature_2m,weather_code",
        "sample_usage": "get_weather(40.7, -74.0)",
    },
    "url_shortener": {
        "description": "Free URL shortener via is.gd",
        "api_url": "https://is.gd/apishorteningreference.php",
        "env_keys": [],
        "example_endpoint": "https://is.gd/create.php?format=simple&url=https://example.com",
        "sample_usage": "shorten_url('https://example.com/long/path')",
    },
}


def list_available_skills() -> str:
    """Show all skills that can be built."""
    lines = [f"# 🛠️ Skill Workshop Catalog ({len(SKILL_CATALOG)} available)\n"]
    
    for name, info in SKILL_CATALOG.items():
        status = "🆕"
        if (APPROVED_DIR / f"{name}.py").exists():
            status = "✅ approved"
        elif (PENDING_DIR / f"{name}.py").exists():
            status = "⏳ pending review"
        elif (REJECTED_DIR / f"{name}.py").exists():
            status = "❌ rejected"
        
        lines.append(f"**{name}** {status}")
        lines.append(f"  {info['description']}")
        if info['env_keys']:
            lines.append(f"  Needs: {', '.join(info['env_keys'])}")
        lines.append("")
    
    return "\n".join(lines)


def build_skill(skill_name: str) -> str:
    """Ask mentor to build a skill, save to _pending, run test."""
    if skill_name not in SKILL_CATALOG:
        return f"❌ Unknown skill '{skill_name}'. Use `list_available_skills` to see options."
    
    info = SKILL_CATALOG[skill_name]
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    
    pending_file = PENDING_DIR / f"{skill_name}.py"
    test_file = PENDING_DIR / f"test_{skill_name}.py"
    
    from brain.mentor import ask_mentor
    
    prompt = f"""Build a Python skill module for Lucy AI assistant.

## Skill: {skill_name}
{info['description']}

## API Reference
Docs: {info['api_url']}
Example endpoint: {info['example_endpoint']}
Required env vars: {', '.join(info['env_keys']) if info['env_keys'] else 'none'}
Sample usage: {info['sample_usage']}

## Requirements
1. Create file at: {pending_file}
2. Create test file at: {test_file}
3. Use `requests` library
4. Load env vars from .env with python-dotenv
5. Return clean markdown-formatted strings for user display
6. Handle errors gracefully — never raise, always return error message string
7. Each function should take simple string/int params

## Code structure for {skill_name}.py
```python
\"\"\"Lucy skill: {skill_name}\"\"\"
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def main_function(param: str = "") -> str:
    \"\"\"Main entry point — returns markdown string.\"\"\"
    try:
        # call API
        # format response
        return "formatted result"
    except Exception as e:
        return f"Error: {{str(e)}}"

# Tool registration metadata — Lucy reads this to register the tool
TOOL_META = {{
    "name": "{skill_name}",
    "description": "{info['description']}",
    "parameters": {{
        "type": "object",
        "properties": {{
            # params here
        }},
    }},
    "function": main_function,
}}
```

## Test file structure
```python
from {skill_name} import main_function, TOOL_META

def test_import():
    assert callable(main_function)
    assert TOOL_META['name'] == '{skill_name}'

def test_call():
    result = main_function()
    assert isinstance(result, str)
    print(f"Result preview: {{result[:200]}}")

if __name__ == '__main__':
    test_import()
    test_call()
    print("✅ All tests passed")
```

Use the Write tool to create both files. Make the code work with real API calls."""
    
    result = ask_mentor(prompt)
    if isinstance(result, dict) and result.get("success"):
        mentor_workspace = result.get("workspace", "")
        
        # Copy files from mentor workspace to pending
        workspace_path = Path(mentor_workspace)
        if workspace_path.exists():
            for src in [workspace_path / f"{skill_name}.py", workspace_path / f"test_{skill_name}.py"]:
                if src.exists():
                    target = PENDING_DIR / src.name
                    target.write_text(src.read_text())
        
        if not pending_file.exists():
            return f"⚠️ Mentor ran but file not found at {pending_file}. Check {mentor_workspace}"
        
        # Run the test
        try:
            test_result = subprocess.run(
                ["python3", str(test_file)],
                cwd=str(PENDING_DIR),
                capture_output=True,
                text=True,
                timeout=30,
            )
            test_ok = test_result.returncode == 0
            test_output = (test_result.stdout + test_result.stderr)[-500:]
        except Exception as e:
            test_ok = False
            test_output = str(e)
        
        preview = pending_file.read_text()[:800]
        
        status = "✅ test passed" if test_ok else "❌ test failed"
        return (
            f"# 🛠️ Built skill: **{skill_name}**\n\n"
            f"**File:** `{pending_file}`\n"
            f"**Status:** {status}\n\n"
            f"**Test output:**\n```\n{test_output}\n```\n\n"
            f"**Code preview:**\n```python\n{preview}\n```\n\n"
            f"---\n"
            f"**To approve:** `approve skill {skill_name}`\n"
            f"**To reject:** `reject skill {skill_name}`\n"
            f"**To rebuild:** `build skill {skill_name}` (will overwrite)"
        )
    else:
        err = result.get("error", "unknown") if isinstance(result, dict) else "unknown"
        return f"❌ Mentor failed: {err}"


def approve_skill(skill_name: str) -> str:
    """Move skill from _pending to _approved and register it."""
    pending_file = PENDING_DIR / f"{skill_name}.py"
    approved_file = APPROVED_DIR / f"{skill_name}.py"
    
    if not pending_file.exists():
        return f"❌ No pending skill '{skill_name}'. Build it first with `build skill {skill_name}`."
    
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    approved_file.write_text(pending_file.read_text())
    
    # Also copy test
    test_src = PENDING_DIR / f"test_{skill_name}.py"
    if test_src.exists():
        (APPROVED_DIR / f"test_{skill_name}.py").write_text(test_src.read_text())
    
    # Clean up pending
    pending_file.unlink()
    if test_src.exists():
        test_src.unlink()
    
    # Try to register the tool dynamically
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(skill_name, str(approved_file))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        
        if hasattr(mod, "TOOL_META"):
            from brain.tools_v2 import register
            meta = mod.TOOL_META
            register(meta["name"], meta["description"], meta["parameters"], meta["function"])
            return f"✅ **{skill_name}** approved and registered. Restart Lucy to activate it in the dashboard."
    except Exception as e:
        return f"⚠️ Approved but auto-registration failed: {e}. Restart Lucy to load manually."
    
    return f"✅ {skill_name} moved to approved. Restart Lucy."


def reject_skill(skill_name: str, reason: str = "") -> str:
    """Move skill from _pending to _rejected."""
    pending_file = PENDING_DIR / f"{skill_name}.py"
    if not pending_file.exists():
        return f"❌ No pending skill '{skill_name}'"
    
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    rejected_file = REJECTED_DIR / f"{skill_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.py"
    rejected_file.write_text(f"# Rejected: {reason}\n\n" + pending_file.read_text())
    pending_file.unlink()
    
    return f"❌ **{skill_name}** rejected. Saved to rejected/ for reference."
