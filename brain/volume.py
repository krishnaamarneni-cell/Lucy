import subprocess
import re

# --- Windows interop helpers --------------------------------------------------

def _run_powershell(script: str, timeout: int = 5) -> tuple[bool, str]:
    """Run a PowerShell command from WSL. Returns (ok, stdout)."""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=timeout,
            cwd="/mnt/c/Windows",  # avoids the UNC path warning
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception:
        return False, ""


def _send_media_key(key_code: int) -> bool:
    """Send a Windows media key via SendKeys."""
    script = f"(New-Object -ComObject WScript.Shell).SendKeys([char]{key_code})"
    ok, _ = _run_powershell(script)
    return ok


# Windows virtual key codes
VK_VOLUME_UP   = 175
VK_VOLUME_DOWN = 174
VK_VOLUME_MUTE = 173
VK_MEDIA_PLAY  = 179
VK_MEDIA_NEXT  = 176
VK_MEDIA_PREV  = 177


# --- CoreAudio PowerShell snippet for exact volume ---------------------------
# Uses a tiny C# helper loaded at runtime to talk to Windows CoreAudio.
# This is the cleanest way to SET or READ exact Windows master volume.

_CORE_AUDIO_CS = r'''
Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {
  int f(); int g(); int h(); int i();
  int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
  int j();
  int GetMasterVolumeLevelScalar(out float pfLevel);
  int k(); int l(); int m(); int n();
  int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, System.Guid pguidEventContext);
  int GetMute(out bool pbMute);
}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice { int Activate(ref System.Guid id, int clsCtx, int ap, out IAudioEndpointVolume aev); }
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator { int f(); int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint); }
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumeratorComObject { }
public class Audio {
  static IAudioEndpointVolume Vol() {
    var enumerator = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator;
    IMMDevice dev = null; Marshal.ThrowExceptionForHR(enumerator.GetDefaultAudioEndpoint(0, 1, out dev));
    IAudioEndpointVolume epv = null; var epvid = typeof(IAudioEndpointVolume).GUID;
    Marshal.ThrowExceptionForHR(dev.Activate(ref epvid, 23, 0, out epv));
    return epv;
  }
  public static float GetVolume() { float v = 0; Vol().GetMasterVolumeLevelScalar(out v); return v; }
  public static void SetVolume(float v) { Vol().SetMasterVolumeLevelScalar(v, System.Guid.Empty); }
}
"@
'''


def _windows_get_volume() -> int | None:
    script = _CORE_AUDIO_CS + "\n[math]::Round([Audio]::GetVolume() * 100)"
    ok, out = _run_powershell(script, timeout=10)
    if not ok or not out.isdigit():
        return None
    return int(out)


def _windows_set_volume(level: int) -> bool:
    level = max(0, min(100, level))
    script = _CORE_AUDIO_CS + f"\n[Audio]::SetVolume({level / 100})"
    ok, _ = _run_powershell(script, timeout=10)
    return ok


# --- pactl fallback (original implementation) --------------------------------

def _pactl_get_volume():
    try:
        result = subprocess.run(
            ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
            capture_output=True, text=True
        )
        match = re.search(r'(\d+)%', result.stdout)
        return int(match.group(1)) if match else None
    except Exception:
        return None


def _pactl_set_volume(level: int):
    level = max(0, min(150, level))
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
    return level


def _pactl_change_volume(delta: int):
    current = _pactl_get_volume() or 50
    new_level = max(0, min(150, current + delta))
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{new_level}%"])
    return new_level


def _pactl_toggle_mute():
    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
    result = subprocess.run(
        ["pactl", "get-sink-mute", "@DEFAULT_SINK@"],
        capture_output=True, text=True
    )
    return "muted" if "yes" in result.stdout else "unmuted"


# --- Public API (unchanged signatures — drop-in replacement) -----------------

def get_volume():
    # Try Windows first, fall back to pactl
    v = _windows_get_volume()
    if v is not None:
        return v
    return _pactl_get_volume()


def set_volume(level: int):
    level = max(0, min(100, level))
    if _windows_set_volume(level):
        return level
    return _pactl_set_volume(level)


def change_volume(delta: int):
    # Media keys step by ~2% each, so send multiple presses for larger changes
    steps = max(1, abs(delta) // 2)
    key = VK_VOLUME_UP if delta > 0 else VK_VOLUME_DOWN
    ok = True
    for _ in range(steps):
        if not _send_media_key(key):
            ok = False
            break
    if ok:
        return get_volume() or 0
    return _pactl_change_volume(delta)


def toggle_mute():
    if _send_media_key(VK_VOLUME_MUTE):
        return "toggled"
    return _pactl_toggle_mute()


def handle_volume(text):
    t = text.lower()

    # Set to specific level
    match = re.search(r'(?:set volume|volume to|set it to)\s+(\d+)', t)
    if match:
        level = set_volume(int(match.group(1)))
        return f"Volume set to {level} percent."

    # Raise by specific amount
    match = re.search(r'(?:volume up|turn up|raise volume|increase volume)\s+(\d+)', t)
    if match:
        new = change_volume(int(match.group(1)))
        return f"Volume raised to {new} percent."

    # Lower by specific amount
    match = re.search(r'(?:volume down|turn down|lower volume|decrease volume)\s+(\d+)', t)
    if match:
        new = change_volume(-int(match.group(1)))
        return f"Volume lowered to {new} percent."

    # Generic up/down
    if any(w in t for w in ["volume up", "turn up", "louder", "raise volume", "increase volume"]):
        new = change_volume(10)
        return f"Volume raised to {new} percent."
    if any(w in t for w in ["volume down", "turn down", "quieter", "lower volume", "decrease volume"]):
        new = change_volume(-10)
        return f"Volume lowered to {new} percent."

    # Mute / unmute
    if any(w in t for w in ["mute", "unmute", "silence"]):
        toggle_mute()
        return "Audio toggled."

    # Query
    if any(w in t for w in ["what's the volume", "current volume", "volume level", "how loud"]):
        level = get_volume()
        return f"Current volume is {level} percent." if level is not None else "I couldn't read the volume."

    return None
