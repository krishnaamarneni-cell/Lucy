import time
import threading
import voice.state as state
from voice.wake import wait_for_wake_word
from voice.stt import listen
from voice.tts import speak
from brain.llm import think
from brain.reminders import start_watcher

SLEEP_TIMEOUT = 30
STOP_WORDS = ["stop", "shut up", "quiet", "enough", "cancel"]

def run():
    start_watcher(speak)  # start reminder background thread
    print("🌙 Lucy is sleeping... say 'Alexa' to wake up")

    while True:
        wait_for_wake_word()
        time.sleep(0.3)
        speak("Hey.")
        while state.is_speaking:
            time.sleep(0.1)

        print("👂 Lucy is awake")
        last_activity = time.time()
        awake = True

        def sleep_watcher():
            nonlocal awake
            while awake:
                time.sleep(1)
                if time.time() - last_activity >= SLEEP_TIMEOUT:
                    print("😴 Going back to sleep...")
                    speak("Going to sleep. Say Alexa when you need me.")
                    awake = False

        watcher = threading.Thread(target=sleep_watcher, daemon=True)
        watcher.start()

        while awake:
            while state.is_speaking:
                time.sleep(0.1)
            user_input = listen(timeout=4)
            if not awake:
                break
            if user_input:
                last_activity = time.time()
                print(f"🗣️ You: {user_input}")
                if any(w in user_input.lower() for w in STOP_WORDS):
                    state.stop_requested = True
                    continue
                if any(w in user_input.lower() for w in ["go to sleep", "goodbye", "bye lucy", "sleep"]):
                    speak("Okay, going to sleep. Bye!")
                    awake = False
                    break
                reply = think(user_input)
                print(f"🤖 Lucy: {reply}")
                speak(reply)
                last_activity = time.time()

if __name__ == "__main__":
    run()
