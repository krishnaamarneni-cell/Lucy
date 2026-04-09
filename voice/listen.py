import os
import wave
import tempfile
import pyaudio
import speech_recognition as sr
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def record_audio(timeout=6, phrase_time_limit=10):
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Speak now...")
        r.adjust_for_ambient_noise(source, duration=0.3)
        audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    return audio.get_wav_data()

def transcribe(wav_data):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_data)
        tmp_path = f.name
    with open(tmp_path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=("audio.wav", f),
            model="whisper-large-v3",
            language="en"
        )
    os.unlink(tmp_path)
    return result.text

def listen():
    wav_data = record_audio()
    return transcribe(wav_data)
