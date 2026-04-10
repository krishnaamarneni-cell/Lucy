"""
Lucy's model configuration.
Supports switching between cloud (Groq) and local (Ollama) models.
"""

import json
from pathlib import Path

CONFIG_FILE = Path.home() / "Lucy" / "model_config.json"

MODELS = {
    "groq": {
        "name": "Groq LLaMA 3.1 8B",
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
        "speed": "~1 sec",
        "cost": "free",
        "needs_internet": True,
    },
    "gemma3-local": {
        "name": "Gemma 3 4B (local)",
        "provider": "ollama",
        "model": "gemma3:4b-it-q4_K_M",
        "speed": "~13 sec",
        "cost": "free",
        "needs_internet": False,
    },
    "gemma4-local": {
        "name": "Gemma 4 E4B (local)",
        "provider": "ollama",
        "model": "gemma4:e4b",
        "speed": "~10-15 sec",
        "cost": "free",
        "needs_internet": False,
    },
}

DEFAULT_MODEL = "groq"


def get_active_model() -> str:
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
            model_id = data.get("active_model", DEFAULT_MODEL)
            if model_id in MODELS:
                return model_id
    except Exception:
        pass
    return DEFAULT_MODEL


def set_active_model(model_id: str) -> bool:
    if model_id not in MODELS:
        return False
    try:
        CONFIG_FILE.write_text(json.dumps({"active_model": model_id}))
        return True
    except Exception:
        return False


def get_model_info() -> dict:
    active = get_active_model()
    return {
        "active": active,
        "models": MODELS,
        "current": MODELS[active],
    }
