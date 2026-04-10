import time
import threading
import voice.state as state
from voice.wake import wait_for_wake_word
from voice.stt import listen
from voice.tts import speak, speak_stream
from brain.llm import think, think_stream
from brain.reminders import start_watcher
from brain import api as lucy_api
from brain import events as lucy_events

SLEEP_TIMEOUT = 30
STOP_WORDS = ["stop", "shut up", "quiet", "enough", "cancel"]

def run():
    start_watcher(speak)  # start reminder background thread

    # Start HTTP API server in a background thread so the dashboard
    # can talk to Lucy while the voice loop runs. Daemon thread means
    # it dies with the main process on Ctrl+C.
    api_thread = threading.Thread(
        target=lucy_api.run,
        kwargs={"host": "127.0.0.1", "port": 8765},
        daemon=True,
        name="LucyAPI",
    )
    api_thread.start()
    time.sleep(0.5)  # give the API a moment to bind

    lucy_events.publish("status.booted", {"voice": True, "api": True})
    print("🌙 Lucy is sleeping... say 'Alexa' to wake up")

    while True:
        wait_for_wake_word()
        time.sleep(0.3)
        speak("Hey.")
        while state.is_speaking:
            time.sleep(0.1)

        print("👂 Lucy is awake")
        lucy_events.publish("voice.awake", {})
        last_activity = time.time()
        awake = True

        def sleep_watcher():
            nonlocal awake
            while awake:
                time.sleep(1)
                if time.time() - last_activity >= SLEEP_TIMEOUT:
                    print("😴 Going back to sleep...")
                    lucy_events.publish("voice.sleeping", {})
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
                lucy_events.publish("voice.transcribed", {"text": user_input})
                if any(w in user_input.lower() for w in STOP_WORDS):
                    state.stop_requested = True
                    continue
                if any(w in user_input.lower() for w in ["go to sleep", "goodbye", "bye lucy", "sleep"]):
                    speak("Okay, going to sleep. Bye!")
                    awake = False
                    break
                # Streaming: Lucy speaks sentences as they're generated

                print(f"🤖 Lucy:", end=" ", flush=True)

                sentences = []

                def _capture(gen):

                    for s in gen:

                        sentences.append(s)

                        print(s, end=" ", flush=True)

                        yield s

                speak_stream(_capture(think_stream(user_input)))

                print()  # newline after streaming complete
                last_activity = time.time()

if __name__ == "__main__":
    run()
