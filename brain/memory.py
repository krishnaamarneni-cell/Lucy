import json
import os

MEMORY_FILE = os.path.expanduser("~/Lucy/memory/memory.json")

def load_memory():
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            return json.load(f)
    return {"user_name": "Krishna", "history": [], "facts": []}

def save_memory(mem):
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=2)

def add_fact(mem, fact):
    if "facts" not in mem:
        mem["facts"] = []
    # Avoid duplicates
    if fact.lower() not in [f.lower() for f in mem["facts"]]:
        mem["facts"].append(fact)
    return mem

def get_context(mem=None):
    if mem is None:
        mem = load_memory()
    lines = []
    if mem.get("user_name"):
        lines.append(f"The user's name is {mem['user_name']}.")
    if mem.get("facts"):
        lines.append("Known facts about the user: " + "; ".join(mem["facts"]) + ".")
    return " ".join(lines)
