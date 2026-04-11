"""
Lucy's website/project builder.
Scaffolds new projects with templates, design system awareness, and deployment.
"""

import os
import subprocess
import re
from pathlib import Path
from datetime import datetime

PROJECTS_DIR = Path.home() / "projects"
DESIGN_SYSTEMS_DIR = Path.home() / "Lucy" / "designs" / "awesome-design-md"


BUILD_TRIGGERS = [
    "build a website", "build a landing page", "build a site",
    "create a website", "create a landing page", "create a project",
    "new project", "scaffold", "build me a",
    "build a saas", "build a blog", "build a portfolio",
    "deploy to vercel", "deploy my site",
]


def needs_builder(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in BUILD_TRIGGERS)


def _run(cmd: str, cwd: str = None, timeout: int = 120) -> tuple:
    """Run a shell command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True,
            text=True, timeout=timeout,
            env={**os.environ, "PATH": f"{Path.home()}/.nvm/versions/node/v20.20.2/bin:" + os.environ.get("PATH", "")},
        )
        return (result.returncode == 0, result.stdout + result.stderr)
    except Exception as e:
        return (False, str(e))


def list_design_systems() -> list:
    """List available design systems from awesome-design-md."""
    if not DESIGN_SYSTEMS_DIR.exists():
        return []
    systems = []
    for item in DESIGN_SYSTEMS_DIR.iterdir():
        if item.is_dir():
            systems.append(item.name)
        elif item.suffix == ".md" and item.stem.lower() != "readme":
            systems.append(item.stem)
    return sorted(systems)


def load_design_system(name: str) -> str:
    """Load a specific design system's DESIGN.md content."""
    name_lower = name.lower().replace(" ", "-")
    candidates = [
        DESIGN_SYSTEMS_DIR / name_lower / "DESIGN.md",
        DESIGN_SYSTEMS_DIR / f"{name_lower}.md",
        DESIGN_SYSTEMS_DIR / name_lower.upper() / "DESIGN.md",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text()
    return ""


def scaffold_nextjs(name: str, design_system: str = "linear") -> dict:
    """Scaffold a new Next.js 15 project with Tailwind and shadcn/ui."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    project_path = PROJECTS_DIR / name
    
    if project_path.exists():
        return {"success": False, "error": f"Project '{name}' already exists"}
    
    log_lines = [f"📦 Creating Next.js project: **{name}**"]
    
    # 1. Run create-next-app
    cmd = f'npx create-next-app@latest {name} --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-turbo --use-npm --yes'
    log_lines.append("1. Running create-next-app...")
    success, output = _run(cmd, cwd=str(PROJECTS_DIR), timeout=300)
    
    if not success:
        return {"success": False, "error": f"Scaffold failed: {output[-500:]}"}
    
    log_lines.append("   ✅ Next.js project created")
    
    # 2. Initialize git
    _run("git init && git add . && git commit -m 'Initial commit'", cwd=str(project_path))
    log_lines.append("2. ✅ Git initialized")
    
    # 3. Load design system for future reference
    design_content = load_design_system(design_system)
    if design_content:
        design_ref = project_path / "DESIGN.md"
        design_ref.write_text(design_content)
        log_lines.append(f"3. ✅ {design_system} design system loaded")
    else:
        log_lines.append(f"3. ⚠️ Design system '{design_system}' not found, using default")
    
    # 4. Create a Lucy-info file for future builds
    info = project_path / ".lucy"
    info.write_text(f"""name: {name}
design_system: {design_system}
created: {datetime.now().isoformat()}
framework: Next.js 15
styling: Tailwind CSS
""")
    
    return {
        "success": True,
        "path": str(project_path),
        "log": "\n".join(log_lines),
        "design_system": design_system,
    }


def generate_landing_page_via_mentor(project_name: str, description: str, design_system: str = "linear") -> str:
    """Use Claude Code mentor to generate a full landing page."""
    from brain.mentor import ask_mentor
    
    project_path = PROJECTS_DIR / project_name
    if not project_path.exists():
        return f"Project '{project_name}' doesn't exist. Create it first."
    
    design_md = load_design_system(design_system)
    design_context = f"\n\n## Design System Reference ({design_system}):\n{design_md[:3000]}" if design_md else ""
    
    task = (
        f"I have a Next.js 15 project at {project_path}. "
        f"Build a complete landing page for: {description}\n\n"
        f"Requirements:\n"
        f"- Replace src/app/page.tsx with a full landing page\n"
        f"- Include: hero section, features (3-6 items), pricing (3 tiers), testimonials, CTA, footer\n"
        f"- Use Tailwind CSS classes only (no external UI library needed)\n"
        f"- Make it mobile-responsive\n"
        f"- Use semantic HTML\n"
        f"- Follow the design system below for typography, colors, and spacing\n"
        f"{design_context}\n\n"
        f"Write the complete src/app/page.tsx file. Keep it clean and production-ready."
    )
    
    result = ask_mentor(task)
    if isinstance(result, dict):
        if result.get("success"):
            return result.get("output", "")
        return f"Mentor error: {result.get('error', 'unknown')}"
    return str(result)


def deploy_to_vercel(project_name: str) -> str:
    """Deploy a project to Vercel."""
    project_path = PROJECTS_DIR / project_name
    if not project_path.exists():
        return f"Project '{project_name}' not found."
    
    success, output = _run("npx vercel --prod --yes", cwd=str(project_path), timeout=300)
    
    if success:
        # Extract the deployment URL
        url_match = re.search(r'https://[^\s]+\.vercel\.app', output)
        url = url_match.group(0) if url_match else "deployed"
        return f"🚀 **Deployed to Vercel:** {url}"
    else:
        return f"Deploy failed: {output[-500:]}"


def handle_builder(text: str) -> str:
    t = text.lower()
    
    # Extract project name
    name_match = re.search(r'(?:called|named|project)\s+([a-z][\w-]*)', t)
    name = name_match.group(1) if name_match else f"project-{datetime.now().strftime('%H%M%S')}"
    
    # Extract design system mention
    design = "linear"  # default
    for system in ["linear", "stripe", "vercel", "notion", "airbnb", "apple", "github"]:
        if system in t:
            design = system
            break
    
    # Scaffold flow
    if any(w in t for w in ["scaffold", "new project", "create project", "build a project"]):
        result = scaffold_nextjs(name, design)
        if result["success"]:
            return f"{result['log']}\n\n📁 Location: `{result['path']}`\n🎨 Design system: {result['design_system']}\n\nNext: `build landing page for {name} about [your product]`"
        return f"❌ {result['error']}"
    
    # Build landing page flow
    if "landing page" in t or "website" in t or "site" in t:
        # Check if a project exists
        existing_projects = [p.name for p in PROJECTS_DIR.iterdir() if p.is_dir()] if PROJECTS_DIR.exists() else []
        
        if not existing_projects:
            # Scaffold first
            result = scaffold_nextjs(name, design)
            if not result["success"]:
                return f"❌ {result['error']}"
            
            # Then generate landing page
            description = text  # full prompt as description
            for prefix in ["build a website", "build a landing page", "create a website", "build a site", "create a landing page"]:
                if prefix in t:
                    description = text[t.index(prefix) + len(prefix):].strip().lstrip("for ").lstrip("about ")
                    break
            
            code = generate_landing_page_via_mentor(name, description or text, design)
            
            return (
                f"{result['log']}\n\n"
                f"**Generating landing page via Claude Code...**\n\n"
                f"{code[:1500]}\n\n"
                f"📁 Project: `{result['path']}`\n"
                f"To run: `cd {result['path']} && npm run dev`\n"
                f"To deploy: `deploy {name} to vercel`"
            )
    
    # Deploy flow
    if "deploy" in t and "vercel" in t:
        return deploy_to_vercel(name)
    
    # List design systems
    if "design system" in t:
        systems = list_design_systems()
        if systems:
            return "**Available design systems:**\n" + "\n".join(f"- {s}" for s in systems[:30])
        return "No design systems found. Run: `git clone https://github.com/user/awesome-design-md ~/Lucy/designs/awesome-design-md`"
    
    return (
        "I can build websites for you. Try:\n"
        "- `scaffold a new project called mysite`\n"
        "- `build a landing page for a SaaS analytics tool`\n"
        "- `deploy project-xyz to vercel`\n"
        "- `list design systems`"
    )
