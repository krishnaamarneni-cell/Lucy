import subprocess
import re

def get_volume():
    try:
        result = subprocess.run(
            ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
            capture_output=True, text=True
        )
        match = re.search(r'(\d+)%', result.stdout)
        return int(match.group(1)) if match else None
    except Exception:
        return None

def set_volume(level: int):
    level = max(0, min(150, level))
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
    return level

def change_volume(delta: int):
    current = get_volume() or 50
    new_level = max(0, min(150, current + delta))
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{new_level}%"])
    return new_level

def toggle_mute():
    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
    result = subprocess.run(
        ["pactl", "get-sink-mute", "@DEFAULT_SINK@"],
        capture_output=True, text=True
    )
    return "muted" if "yes" in result.stdout else "unmuted"

def handle_volume(text):
    t = text.lower()

    # Set to specific level: "set volume to 70"
    match = re.search(r'(?:set volume|volume to|set it to)\s+(\d+)', t)
    if match:
        level = set_volume(int(match.group(1)))
        return f"Volume set to {level} percent."

    # Raise by specific amount: "volume up 20"
    match = re.search(r'(?:volume up|turn up|raise volume|increase volume)\s+(\d+)', t)
    if match:
        new = change_volume(int(match.group(1)))
        return f"Volume raised to {new} percent."

    # Lower by specific amount: "volume down 20"
    match = re.search(r'(?:volume down|turn down|lower volume|decrease volume)\s+(\d+)', t)
    if match:
        new = change_volume(-int(match.group(1)))
        return f"Volume lowered to {new} percent."

    # Generic up/down (10% step)
    if any(w in t for w in ["volume up", "turn up", "louder", "raise volume", "increase volume"]):
        new = change_volume(10)
        return f"Volume raised to {new} percent."
    if any(w in t for w in ["volume down", "turn down", "quieter", "lower volume", "decrease volume"]):
        new = change_volume(-10)
        return f"Volume lowered to {new} percent."

    # Mute / unmute
    if any(w in t for w in ["mute", "unmute", "silence"]):
        state = toggle_mute()
        return f"Audio {state}."

    # What's the volume?
    if any(w in t for w in ["what's the volume", "current volume", "volume level", "how loud"]):
        level = get_volume()
        return f"Current volume is {level} percent." if level else "I couldn't read the volume."

    return None
