import asyncio
import subprocess
import edge_tts
import pygame
import tempfile
import os
import re
import time
import voice.state as state

VOICE = "en-US-JennyNeural"

def split_sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]

async def _speak_chunk(text, path):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(path)

def speak(text):
    state.is_speaking = True
    state.stop_requested = False
    # Ensure WSLg audio sink is unmuted (WSL quirk — sink can re-mute itself)
    try:
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"],
                       capture_output=True, timeout=2)
    except Exception:
        pass
    pygame.mixer.init()

    for sentence in split_sentences(text):
        if state.stop_requested:
            print("🛑 Speech interrupted!")
            break
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            tmp_path = f.name
        asyncio.run(_speak_chunk(sentence, tmp_path))
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if state.stop_requested:
                pygame.mixer.music.stop()
                break
            pygame.time.Clock().tick(10)
        os.remove(tmp_path)

    pygame.mixer.quit()
    time.sleep(1.5)  # buffer so mic doesn't catch Lucy's voice
    state.is_speaking = False
    state.stop_requested = False
