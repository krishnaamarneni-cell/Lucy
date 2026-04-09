import groq
import os
import time
import tempfile
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
from dotenv import load_dotenv
import voice.state as state

load_dotenv()
client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
SAMPLE_RATE = 16000
JUNK = {".", "see", "see.", "hello.", "bye", "thanks", "thank you",
        "you", "be", "the", "sí", "si", "el", "them", "a", "i", "oh", "uh", "goodbye"}

def listen(timeout=5):
    while state.is_speaking:
        time.sleep(0.1)

    print(f"🎙️ Listening ({timeout}s)...")
    try:
        audio = sd.rec(int(timeout * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                       channels=1, dtype='int16')
        sd.wait()

        if np.abs(audio).mean() < 500:
            return None

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            wav.write(f.name, SAMPLE_RATE, audio)
            tmp_path = f.name

        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                response_format="text",
                language="en"
            )
        os.remove(tmp_path)
        text = result.strip()
        clean = text.lower().strip(".!?,")

        if len(clean) < 3 or clean in JUNK:
            return None
        return text

    except Exception as e:
        print(f"STT error: {e}")
        return None
