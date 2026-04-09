import pyaudio
import numpy as np
from openwakeword.model import Model

CHUNK = 1280
RATE = 16000
MODEL_PATH = "/home/krishna/Lucy/models/alexa.onnx"
THRESHOLD = 0.4  # lowered from 0.5 — more forgiving for morning voices / quiet rooms

def wait_for_wake_word():
    model = Model(wakeword_model_paths=[MODEL_PATH])  # no inference_framework
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=1,
                        rate=RATE, input=True, frames_per_buffer=CHUNK)
    print("🌙 Waiting for wake word... (say 'Alexa')")
    try:
        while True:
            pcm = stream.read(CHUNK, exception_on_overflow=False)
            samples = np.frombuffer(pcm, dtype=np.int16)
            prediction = model.predict(samples)
            score = list(prediction.values())[0]
            # Debug: log near-misses so you can see if Lucy almost heard you
            if 0.2 < score <= THRESHOLD:
                print(f"🤔 Near miss (score: {score:.2f}) — try again a bit clearer")
            if score > THRESHOLD:
                print(f"✅ Wake word detected! (score: {score:.2f})")
                model.reset()
                break
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
