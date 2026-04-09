import asyncio
import edge_tts
import subprocess
import tempfile
import os

async def _synthesize(text, voice="en-US-JennyNeural"):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        mp3_file = f.name
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(mp3_file)
    return mp3_file

def speak(text):
    print(f"Lucy: {text}")
    mp3_file = asyncio.run(_synthesize(text))
    wav_file = mp3_file.replace(".mp3", ".wav")
    subprocess.run(["ffmpeg", "-i", mp3_file, wav_file, "-y", "-loglevel", "quiet"])
    win_path = subprocess.check_output(["wslpath", "-w", wav_file]).decode().strip()
    ps_script = f"(New-Object System.Media.SoundPlayer '{win_path}').PlaySync()"
    subprocess.run(["powershell.exe", "-c", ps_script])
    os.unlink(mp3_file)
    os.unlink(wav_file)
