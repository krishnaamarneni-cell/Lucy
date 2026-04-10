"""
Lucy's text-to-speech module.

Uses edge_tts for high-quality neural voice synthesis, then plays audio
through Windows' native SoundPlayer (via PowerShell) instead of pygame/
PulseAudio. This bypasses the WSLg audio sink entirely and is far more
reliable than the pygame approach.

Requires: ffmpeg, PowerShell (Windows interop), edge_tts
"""

import asyncio
import os
import re
import subprocess
import tempfile
import time

import edge_tts

import voice.state as state

VOICE = "en-US-JennyNeural"

# Keep a handle on the currently-playing PowerShell process so we can kill
# it if the user says "stop" mid-speech.
_current_proc = None


def split_sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


async def _synthesize(text, path):
    """Generate an MP3 file from text using Edge TTS."""
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(path)


def _convert_to_wav(mp3_path):
    """Convert MP3 to WAV (SoundPlayer only handles WAV)."""
    wav_path = mp3_path.replace(".mp3", ".wav")
    subprocess.run(
        ["ffmpeg", "-i", mp3_path, wav_path, "-y", "-loglevel", "quiet"],
        check=True,
    )
    return wav_path


def _play_wav_windows(wav_path):
    """Play a WAV file through Windows' native SoundPlayer.

    Returns the subprocess so the caller can wait on or kill it.
    """
    win_path = subprocess.check_output(["wslpath", "-w", wav_path]).decode().strip()
    # Use single quotes inside PowerShell and escape any in the path (rare).
    safe_path = win_path.replace("'", "''")
    ps_script = f"(New-Object System.Media.SoundPlayer '{safe_path}').PlaySync()"
    return subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-Command", ps_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop_current():
    """Kill the current PowerShell playback process if one is running."""
    global _current_proc
    if _current_proc and _current_proc.poll() is None:
        try:
            _current_proc.terminate()
            _current_proc.wait(timeout=1)
        except Exception:
            try:
                _current_proc.kill()
            except Exception:
                pass
    _current_proc = None


def speak(text):
    """Speak text aloud, one sentence at a time, respecting stop_requested."""
    global _current_proc
    state.is_speaking = True
    state.stop_requested = False

    try:
        for sentence in split_sentences(text):
            if state.stop_requested:
                print("🛑 Speech interrupted!")
                break

            mp3_path = None
            wav_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                    mp3_path = f.name

                asyncio.run(_synthesize(sentence, mp3_path))
                wav_path = _convert_to_wav(mp3_path)

                proc = _play_wav_windows(wav_path)
                _current_proc = proc

                # Poll for completion or stop request (use local ref to avoid races)
                while proc.poll() is None:
                    if state.stop_requested:
                        _stop_current()
                        break
                    time.sleep(0.05)

                _current_proc = None
            finally:
                for p in (mp3_path, wav_path):
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
    finally:
        # Small buffer so the mic doesn't catch Lucy's own voice as input
        time.sleep(0.8)
        state.is_speaking = False
        state.stop_requested = False


def speak_stream(sentence_iter):
    """
    Streaming version of speak(). Takes a generator that yields sentences
    and speaks each one as soon as it arrives.

    This is what kills dead air — Lucy starts speaking sentence 1 while
    the LLM is still generating sentence 3.
    """
    global _current_proc
    state.is_speaking = True
    state.stop_requested = False

    spoke_anything = False
    try:
        for sentence in sentence_iter:
            if not sentence or not sentence.strip():
                continue
            if state.stop_requested:
                print("🛑 Speech interrupted!")
                break

            # Split the streamed sentence further in case it contains multiple
            # (the LLM sometimes yields "Sentence one. Sentence two." together)
            for s in split_sentences(sentence):
                if state.stop_requested:
                    break
                mp3_path = None
                wav_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                        mp3_path = f.name

                    asyncio.run(_synthesize(s, mp3_path))
                    wav_path = _convert_to_wav(mp3_path)

                    proc = _play_wav_windows(wav_path)
                    _current_proc = proc
                    spoke_anything = True

                    while proc.poll() is None:
                        if state.stop_requested:
                            _stop_current()
                            break
                        time.sleep(0.05)
                    _current_proc = None
                finally:
                    for p in (mp3_path, wav_path):
                        if p and os.path.exists(p):
                            try:
                                os.remove(p)
                            except Exception:
                                pass
    finally:
        if spoke_anything:
            time.sleep(0.8)  # mic buffer
        state.is_speaking = False
        state.stop_requested = False
