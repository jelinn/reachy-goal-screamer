"""Tracked-clubs configuration, persisted as JSON in the user's home dir."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / ".goal_screamer" / "clubs.json"

DEFAULT_CLUBS = [
    {"league": "usa.1", "team_id": "21812", "name": "St. Louis CITY SC"},
]

_lock = threading.Lock()


def load_clubs() -> list[dict]:
    with _lock:
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                logger.exception("Bad config file, falling back to defaults")
        return list(DEFAULT_CLUBS)


def save_clubs(clubs: list[dict]) -> None:
    with _lock:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(clubs, indent=2))


def add_club(league: str, team_id: str, name: str) -> list[dict]:
    clubs = load_clubs()
    if not any(c["team_id"] == team_id for c in clubs):
        clubs.append({"league": league, "team_id": team_id, "name": name})
        save_clubs(clubs)
    return clubs


def remove_club(team_id: str) -> list[dict]:
    clubs = [c for c in load_clubs() if c["team_id"] != team_id]
    save_clubs(clubs)
    return clubs
