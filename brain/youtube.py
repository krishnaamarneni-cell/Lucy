"""
Lucy's YouTube integration.
Track channels, get latest videos, summarize transcripts.
"""

import json
from pathlib import Path
from brain.google_auth import get_youtube_service

CHANNELS_FILE = Path.home() / "Lucy" / "memory" / "youtube_channels.json"

YOUTUBE_TRIGGERS = [
    "youtube", "video", "videos", "channel", "channels",
    "watch", "latest video", "new video", "subscribe",
    "transcript", "what's the video about",
    "fireship", "networkchuck", "primeagen",
]


def needs_youtube(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in YOUTUBE_TRIGGERS)


def _load_channels() -> list:
    try:
        if CHANNELS_FILE.exists():
            return json.loads(CHANNELS_FILE.read_text())
    except Exception:
        pass
    return []


def _save_channels(channels: list):
    CHANNELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHANNELS_FILE.write_text(json.dumps(channels, indent=2))


def add_channel(channel_name: str) -> str:
    service = get_youtube_service()
    results = service.search().list(
        part="snippet", q=channel_name, type="channel", maxResults=1
    ).execute()

    items = results.get("items", [])
    if not items:
        return f"Couldn't find a YouTube channel named '{channel_name}'."

    channel = items[0]
    channel_id = channel["snippet"]["channelId"]
    title = channel["snippet"]["title"]

    channels = _load_channels()
    if any(c["id"] == channel_id for c in channels):
        return f"Already tracking **{title}**."

    channels.append({"id": channel_id, "name": title})
    _save_channels(channels)
    return f"Now tracking **{title}**. I'll check their latest videos when you ask."


def list_channels() -> str:
    channels = _load_channels()
    if not channels:
        return "Not tracking any YouTube channels yet. Say 'track Fireship on YouTube' to add one."

    lines = ["**Tracked YouTube channels:**\n"]
    for i, c in enumerate(channels, 1):
        lines.append(f"{i}. **{c['name']}**")
    return "\n".join(lines)


def get_latest_videos(max_per_channel: int = 3) -> str:
    channels = _load_channels()
    if not channels:
        return "Not tracking any channels. Say 'track Fireship on YouTube' to start."

    service = get_youtube_service()
    lines = ["**Latest videos from your channels:**\n"]

    for ch in channels:
        try:
            results = service.search().list(
                part="snippet", channelId=ch["id"],
                order="date", maxResults=max_per_channel, type="video"
            ).execute()

            videos = results.get("items", [])
            lines.append(f"**{ch['name']}**")
            if videos:
                for v in videos:
                    title = v["snippet"]["title"]
                    vid_id = v["id"]["videoId"]
                    date = v["snippet"]["publishedAt"][:10]
                    lines.append(f"- [{title}](https://youtube.com/watch?v={vid_id}) ({date})")
            else:
                lines.append("- No recent videos")
            lines.append("")
        except Exception as e:
            lines.append(f"**{ch['name']}** — error fetching: {str(e)}")

    return "\n".join(lines)


def get_video_summary(video_url: str) -> str:
    import re
    match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', video_url)
    if not match:
        return "Couldn't find a valid YouTube video ID in that URL."

    video_id = match.group(1)

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join(entry["text"] for entry in transcript)[:4000]

        # Summarize via Groq
        import os
        from groq import Groq
        from dotenv import load_dotenv
        load_dotenv()

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": (
                    f"Summarize this YouTube video transcript clearly:\n\n{text}\n\n"
                    f"FORMAT: Use ## for the title, bullet points for key topics, "
                    f"and a one-line takeaway at the end. Max 10 bullet points."
                )
            }],
        )
        return response.choices[0].message.content.strip()
    except ImportError:
        return "YouTube transcript library not installed. Run: pip install youtube-transcript-api"
    except Exception as e:
        return f"Couldn't get transcript: {str(e)}. The video may not have captions."


def handle_youtube(text: str) -> str:
    t = text.lower()

    if any(w in t for w in ["track", "add channel", "follow", "subscribe"]):
        # Extract channel name
        for prefix in ["track", "add channel", "follow", "subscribe to", "add"]:
            if prefix in t:
                name = text[t.index(prefix) + len(prefix):].strip()
                name = name.replace("on youtube", "").replace("youtube", "").strip()
                if name:
                    return add_channel(name)
        return "Which channel? Say 'track Fireship on YouTube'"

    if any(w in t for w in ["my channels", "list channels", "tracked channels", "what channels"]):
        return list_channels()

    if any(w in t for w in ["latest video", "new video", "what's new", "updates", "recent"]):
        return get_latest_videos()

    if any(w in t for w in ["summary", "summarize", "what's this video", "about this video"]):
        import re
        urls = re.findall(r'https?://[^\s]+', text)
        if urls:
            return get_video_summary(urls[0])
        return "Paste a YouTube URL and I'll summarize it for you."

    # Default: check for channel name to track or show latest
    channels = _load_channels()
    if channels:
        return get_latest_videos()
    return "I can track YouTube channels for you. Say 'track Fireship on YouTube' to start, then ask 'what's new on YouTube' anytime."
