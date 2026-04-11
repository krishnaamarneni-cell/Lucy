"""
Lucy's music player.
Opens songs in your Windows browser via wslview.
"""

import subprocess
import urllib.parse

MUSIC_TRIGGERS = [
    "play song", "play music", "play ", "play some",
    "put on", "open youtube", "play on youtube",
    "i want to listen", "music please", "song please",
]


def needs_music(text: str) -> bool:
    t = text.lower()
    # "play" needs to be followed by something that sounds like music
    if any(trigger in t for trigger in MUSIC_TRIGGERS):
        # Don't trigger on "play this video" (already a URL) or "play the game"
        if "http" in t or "game" in t:
            return False
        return True
    return False


def play_song(query: str) -> str:
    """Search YouTube and auto-play the top result in Windows browser."""
    q = query.lower()
    for prefix in ["play song", "play music", "play some", "play ", "put on ", 
                   "i want to listen to ", "can you play ", "music please"]:
        if q.startswith(prefix):
            q = q[len(prefix):].strip()
            break
    
    if not q:
        return "What song should I play?"
    
    # Use YouTube API to get the first video ID, then open the direct watch URL
    try:
        from brain.google_auth import get_youtube_service
        service = get_youtube_service()
        results = service.search().list(
            part="snippet", q=q, type="video", maxResults=1
        ).execute()
        
        items = results.get("items", [])
        if items:
            video_id = items[0]["id"]["videoId"]
            title = items[0]["snippet"]["title"]
            # Direct watch URL auto-plays
            watch_url = f"https://music.youtube.com/watch?v={video_id}"
            subprocess.run(["wslview", watch_url], timeout=5, check=True)
            return f"🎵 Playing **{title}**"
    except Exception as e:
        pass
    
    # Fallback to search results page
    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}"
    try:
        subprocess.run(["wslview", search_url], timeout=5, check=True)
        return f"🎵 Opened YouTube search for **{q}** (click the first result to play)"
    except Exception as e:
        return f"Couldn't open browser: {str(e)}"


def handle_music(text: str) -> str:
    return play_song(text)
