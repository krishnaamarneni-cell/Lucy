import sys
sys.path.insert(0, '.')
import speech_recognition as sr
from voice.speak import speak

r = sr.Recognizer()
speak("I am listening")
with sr.Microphone() as source:
    print("Speak now...")
    r.adjust_for_ambient_noise(source, duration=1)
    audio = r.listen(source, timeout=5)

text = r.recognize_google(audio)
print(f"You said: {text}")
speak(f"You said: {text}")
