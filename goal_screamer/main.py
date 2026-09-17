"""GOAL! — Reachy Mini celebrates when your clubs score.

Set FAKE_MATCH=1 to run a scripted demo match instead of polling ESPN.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time

from pydantic import BaseModel
from reachy_mini import ReachyMini, ReachyMiniApp

from . import audio, config, moves
from .scores import (
    LEAGUES,
    MatchEvent,
    MatchTracker,
    fetch_scoreboard,
    fetch_teams,
    parse_matches,
)

logger = logging.getLogger(__name__)

POLL_LIVE_S = 20
POLL_IDLE_S = 60
MAX_BACKOFF_S = 300


class ClubIn(BaseModel):
    league: str
    team_id: str
    name: str


class GoalScreamer(ReachyMiniApp):
    custom_app_url: str | None = "http://0.0.0.0:8042"
    # No video needed; saves CPU on the wireless.
    request_media_backend: str | None = "gstreamer_no_video"

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        events: queue.Queue[MatchEvent] = queue.Queue()
        tracker = MatchTracker()
        self._register_settings_routes(events)

        threading.Thread(
            target=self._fake_match if os.environ.get("FAKE_MATCH") else self._poll_loop,
            args=(events, tracker, stop_event),
            daemon=True,
        ).start()

        threading.Thread(
            target=self._warm_tts_cache, args=(stop_event,), daemon=True
        ).start()

        t0 = time.time()
        while not stop_event.is_set():
            try:
                event = events.get_nowait()
            except queue.Empty:
                targets = moves.idle_targets(time.time() - t0, tracker.has_live_match())
                reachy_mini.set_target(**targets)
                time.sleep(0.02)
                continue
            self._react(reachy_mini, stop_event, event)

    def _react(self, mini: ReachyMini, stop_event: threading.Event, event: MatchEvent):
        logger.info(
            "%s: %s %d-%d %s",
            event.kind, event.team_name, event.our_score, event.opp_score, event.opponent_name,
        )
        audio.announce(mini, event.kind, event.team_name, event.result)
        if event.kind == "goal_for":
            moves.celebrate_goal(mini, stop_event)
        elif event.kind == "goal_against":
            moves.sad_slump(mini, stop_event)
        elif event.kind == "kickoff":
            moves.perk_up(mini, stop_event)
        elif event.kind == "fulltime":
            if event.result == "win":
                moves.victory_dance(mini, stop_event)
            elif event.result == "loss":
                moves.defeat_slump(mini, stop_event)
            else:
                moves.shrug(mini, stop_event)

    def _poll_loop(self, events: queue.Queue, tracker: MatchTracker, stop_event: threading.Event):
        backoff = 1
        while not stop_event.is_set():
            leagues: dict[str, dict[str, str]] = {}
            for club in config.load_clubs():
                leagues.setdefault(club["league"], {})[club["team_id"]] = club["name"]
            try:
                snapshots = []
                for league, team_ids in leagues.items():
                    snapshots.extend(parse_matches(fetch_scoreboard(league), team_ids))
                for event in tracker.update(snapshots):
                    events.put(event)
                backoff = 1
            except Exception as e:
                # Wi-Fi drops and ESPN hiccups must never kill the loop.
                logger.warning("Poll failed (%s); retrying in %ss", e, backoff)
                if stop_event.wait(backoff):
                    return
                backoff = min(backoff * 2, MAX_BACKOFF_S)
                continue
            stop_event.wait(POLL_LIVE_S if tracker.has_live_match() else POLL_IDLE_S)

    def _fake_match(self, events: queue.Queue, tracker: MatchTracker, stop_event: threading.Event):
        """Scripted demo: kickoff → goal → concede → goal → win."""
        clubs = config.load_clubs()
        team = clubs[0]["name"] if clubs else "St. Louis CITY SC"

        def ev(kind, ours, theirs, result=None):
            return MatchEvent(
                kind=kind, team_name=team, opponent_name="Demo FC",
                our_score=ours, opp_score=theirs, result=result,
            )

        script = [
            (3, ev("kickoff", 0, 0)),
            (8, ev("goal_for", 1, 0)),
            (18, ev("goal_against", 1, 1)),
            (26, ev("goal_for", 2, 1)),
            (34, ev("fulltime", 2, 1, "win")),
        ]
        logger.info("FAKE_MATCH mode: scripted demo for %s", team)
        t0 = time.time()
        for at, event in script:
            if stop_event.wait(max(0.0, at - (time.time() - t0))):
                return
            events.put(event)

    def _warm_tts_cache(self, stop_event: threading.Event):
        for club in config.load_clubs():
            if stop_event.is_set():
                return
            audio.pregenerate_for_team(club["name"])

    def _register_settings_routes(self, events: queue.Queue):
        if self.settings_app is None:
            return

        @self.settings_app.get("/api/clubs")
        def get_clubs():
            return config.load_clubs()

        @self.settings_app.post("/api/clubs")
        def post_club(club: ClubIn):
            clubs = config.add_club(club.league, club.team_id, club.name)
            threading.Thread(
                target=audio.pregenerate_for_team, args=(club.name,), daemon=True
            ).start()
            return clubs

        @self.settings_app.delete("/api/clubs/{team_id}")
        def delete_club(team_id: str):
            return config.remove_club(team_id)

        @self.settings_app.get("/api/leagues")
        def get_leagues():
            return [{"slug": slug, "name": name} for slug, name in LEAGUES.items()]

        @self.settings_app.get("/api/leagues/{league}/teams")
        def get_league_teams(league: str):
            return fetch_teams(league)

        @self.settings_app.post("/api/test/{kind}")
        def test_event(kind: str):
            clubs = config.load_clubs()
            team = clubs[0]["name"] if clubs else "St. Louis CITY SC"
            result = {"win": "win"}.get(kind)
            if kind == "fulltime":
                result = "win"
            events.put(
                MatchEvent(
                    kind=kind, team_name=team, opponent_name="Test FC",
                    our_score=1, opp_score=0, result=result,
                )
            )
            return {"queued": kind}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = GoalScreamer()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
