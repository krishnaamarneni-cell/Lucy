"""
Lucy's HTTP API server.

Exposes Lucy's brain over HTTP + WebSocket so the dashboard can:
  - Send chat messages
  - Read and change mode
  - Kill current operations (emergency stop)
  - Watch a live stream of events

The API runs on localhost:8765 by default. It's started by main.py in a
background thread alongside the voice loop.
"""

import asyncio
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from brain import events
from brain.mode import (
    get_mode,
    set_mode,
    PermissionDeniedError,
    VALID_MODES,
    check_action,
)
from brain.model_config import get_model_info, set_active_model, get_active_model

# ---------------------------------------------------------------------------
# Auth token — generated on first run, persisted to ~/Lucy/.api_token
# The dashboard reads this file to authenticate.
# ---------------------------------------------------------------------------

TOKEN_FILE = Path.home() / "Lucy" / ".api_token"


def _get_or_create_token() -> str:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token)
    return token


API_TOKEN = _get_or_create_token()


def _check_auth(authorization: str | None) -> None:
    """Raise 401 if the bearer token doesn't match."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------------------------------------------------------------------
# Lifespan — publish startup and shutdown events
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    events.publish("api.started", {"version": "1.0"})
    yield
    events.publish("api.stopped", {})


app = FastAPI(title="Lucy API", version="1.0", lifespan=lifespan)

# Allow the dashboard (localhost:3000 for Next.js dev, or any localhost port)
# to talk to the API. In production we'd lock this down further.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    speak: bool = True  # if True, Lucy also speaks the response aloud


class ChatResponse(BaseModel):
    reply: str
    mode: str


class ModeRequest(BaseModel):
    mode: str


class ModeResponse(BaseModel):
    mode: str


class StatusResponse(BaseModel):
    running: bool
    mode: str
    speaking: bool
    subscribers: int


# Emergency stop flag — any long-running operation should check this
_stop_flag = asyncio.Event()


def is_stopped() -> bool:
    return _stop_flag.is_set()


def clear_stop() -> None:
    _stop_flag.clear()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/status", response_model=StatusResponse)
def status(authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    # Import lazily so we don't require voice.state at import time
    try:
        import voice.state as state
        speaking = bool(getattr(state, "is_speaking", False))
    except Exception:
        speaking = False
    return StatusResponse(
        running=True,
        mode=get_mode(),
        speaking=speaking,
        subscribers=events.subscriber_count(),
    )


@app.get("/mode", response_model=ModeResponse)
def get_current_mode(authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    return ModeResponse(mode=get_mode())


@app.post("/mode", response_model=ModeResponse)
def change_mode(req: ModeRequest, authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    if req.mode not in VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Must be one of: {list(VALID_MODES)}",
        )
    old = get_mode()
    set_mode(req.mode)
    events.publish("mode.changed", {"from": old, "to": req.mode})
    return ModeResponse(mode=req.mode)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    # Clear any previous stop flag
    clear_stop()
    events.publish("chat.received", {"message": req.message})

    # Lazy import to avoid cycles at module load
    from brain.llm import think

    try:
        reply = think(req.message, chat_mode=True)
    except PermissionDeniedError as e:
        events.publish("action.denied", {"reason": str(e), "action": req.message})
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        events.publish("error", {"message": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

    events.publish("chat.replied", {"reply": reply})

    # Speak aloud if requested and not stopped
    if req.speak and not is_stopped():
        try:
            from voice.tts import speak
            speak(reply)
        except Exception as e:
            events.publish("error", {"message": f"TTS failed: {e}"})

    return ChatResponse(reply=reply, mode=get_mode())


@app.get("/model")
async def model_info():
    return get_model_info()

@app.post("/model")
async def change_model(body: dict):
    model_id = body.get("model_id", "")
    if set_active_model(model_id):
        info = get_model_info()
        bus.publish("model.changed", {"model": model_id, "name": info["current"]["name"]})
        return info
    raise HTTPException(status_code=400, detail=f"Unknown model: {model_id}")

@app.post("/stop")
def emergency_stop(authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    _stop_flag.set()
    # Also tell TTS to interrupt any current speech
    try:
        import voice.state as state
        state.stop_requested = True
    except Exception:
        pass
    events.publish("stop.triggered", {})
    return {"stopped": True}


@app.get("/events/history")
def event_history(
    limit: int = 50,
    authorization: str | None = Header(default=None),
):
    _check_auth(authorization)
    return {"events": events.get_history(limit=limit)}


@app.websocket("/events/stream")
async def event_stream(websocket: WebSocket, token: str = ""):
    """
    WebSocket endpoint for the dashboard to receive live events.
    Auth: the token is passed as a query param ?token=... because browser
    WebSockets don't easily support custom headers.
    """
    if not secrets.compare_digest(token, API_TOKEN):
        await websocket.close(code=1008, reason="Invalid token")
        return

    await websocket.accept()
    queue = events.subscribe()
    try:
        # Send recent history first so the UI can hydrate
        for ev in events.get_history(limit=20):
            await websocket.send_json(ev)
        # Then stream live events
        while True:
            ev = await queue.get()
            await websocket.send_json(ev)
    except WebSocketDisconnect:
        pass
    finally:
        events.unsubscribe(queue)


# ---------------------------------------------------------------------------
# Standalone runner (for testing without main.py)
# ---------------------------------------------------------------------------

def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the API server. Called by main.py in a background thread."""
    import uvicorn
    print(f"🌐 Lucy API on http://{host}:{port}")
    print(f"🔑 Token stored at {TOKEN_FILE}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run()
