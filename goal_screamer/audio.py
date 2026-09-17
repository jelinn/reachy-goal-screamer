"""Text-to-speech announcements, generated with gTTS and cached as mp3.

Files are generated when a club is added (and lazily on first use), then
played through the robot's speaker via the SDK's play_sound (GStreamer
playbin decodes mp3 natively).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".goal_screamer" / "sounds"


def phrase_for(kind: str, team_name: str, result: str | None = None) -> str:
    if kind == "goal_for":
        return f"Goooooool! Goooool for {team_name}!"
    if kind == "goal_against":
        return "Ohhh no. They scored."
    if kind == "kickoff":
        return f"Kick off! Come on {team_name}!"
    if kind == "fulltime":
        if result == "win":
            return f"Full time! {team_name} win! What a result!"
        if result == "loss":
            return f"Full time. A tough loss for {team_name}."
        return "Full time. All square. A draw."
    return ""


def _cache_path(text: str) -> Path:
    digest = hashlib.sha1(text.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{digest}.mp3"


def ensure_sound(text: str) -> Path | None:
    """Generate (if needed) and return the cached mp3 for this phrase."""
    path = _cache_path(text)
    if path.exists():
        return path
    try:
        from gtts import gTTS

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        gTTS(text=text, lang="en", slow=False).save(str(path))
        logger.info("Generated TTS: %r -> %s", text, path.name)
        return path
    except Exception:
        logger.exception("TTS generation failed for %r", text)
        return None


def pregenerate_for_team(team_name: str) -> None:
    """Warm the cache for every phrase involving this team."""
    for kind, result in [
        ("goal_for", None),
        ("goal_against", None),
        ("kickoff", None),
        ("fulltime", "win"),
        ("fulltime", "loss"),
        ("fulltime", "draw"),
    ]:
        text = phrase_for(kind, team_name, result)
        if text:
            ensure_sound(text)


def announce(mini, kind: str, team_name: str, result: str | None = None) -> None:
    """Play the phrase for this event; never raises."""
    text = phrase_for(kind, team_name, result)
    if not text:
        return
    path = ensure_sound(text)
    if path is None:
        return
    try:
        mini.media.play_sound(str(path))
    except Exception:
        logger.exception("play_sound failed for %s", path)
