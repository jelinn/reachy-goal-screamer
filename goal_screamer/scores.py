"""ESPN soccer scoreboard client and match state machine.

All knowledge of the (unofficial) ESPN API shape lives in this module so a
shape change is a one-file fix.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# League slug -> display name, for the settings UI dropdown.
LEAGUES = {
    "usa.1": "MLS",
    "eng.1": "Premier League",
    "esp.1": "La Liga",
    "ger.1": "Bundesliga",
    "ita.1": "Serie A",
    "fra.1": "Ligue 1",
    "mex.1": "Liga MX",
    "uefa.champions": "Champions League",
    "usa.open": "US Open Cup",
    "concacaf.champions": "Concacaf Champions Cup",
}


@dataclass(frozen=True)
class MatchSnapshot:
    """One tracked team's view of one match at one poll."""

    event_id: str
    team_id: str
    team_name: str
    opponent_name: str
    our_score: int
    opp_score: int
    state: str  # "pre" | "in" | "post"


@dataclass(frozen=True)
class MatchEvent:
    kind: str  # "kickoff" | "goal_for" | "goal_against" | "fulltime"
    team_name: str
    opponent_name: str
    our_score: int
    opp_score: int
    result: str | None = None  # for fulltime: "win" | "loss" | "draw"


def fetch_scoreboard(league: str, timeout: float = 10.0) -> dict:
    resp = requests.get(f"{BASE_URL}/{league}/scoreboard", timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_teams(league: str, timeout: float = 10.0) -> list[dict]:
    """Return [{"id": ..., "name": ...}] for the settings UI."""
    resp = requests.get(f"{BASE_URL}/{league}/teams", timeout=timeout)
    resp.raise_for_status()
    teams = resp.json()["sports"][0]["leagues"][0]["teams"]
    return [{"id": t["team"]["id"], "name": t["team"]["displayName"]} for t in teams]


def parse_matches(scoreboard: dict, team_ids: dict[str, str]) -> list[MatchSnapshot]:
    """Extract snapshots for tracked teams. team_ids maps team id -> team name."""
    snapshots = []
    for event in scoreboard.get("events", []):
        try:
            competition = event["competitions"][0]
            state = event["status"]["type"]["state"]
            competitors = competition["competitors"]
            for competitor in competitors:
                team = competitor["team"]
                if team["id"] not in team_ids:
                    continue
                opponent = next(c for c in competitors if c is not competitor)
                snapshots.append(
                    MatchSnapshot(
                        event_id=str(event["id"]),
                        team_id=team["id"],
                        team_name=team_ids[team["id"]],
                        opponent_name=opponent["team"]["displayName"],
                        our_score=int(competitor.get("score") or 0),
                        opp_score=int(opponent.get("score") or 0),
                        state=state,
                    )
                )
        except (KeyError, IndexError, ValueError, StopIteration) as e:
            logger.warning("Skipping malformed event: %s", e)
    return snapshots


class MatchTracker:
    """Diffs successive snapshots into events.

    A match first seen in progress sets a score baseline without emitting
    goal events, so restarting the app mid-match never replays old goals.
    """

    def __init__(self):
        self._last: dict[str, MatchSnapshot] = {}
        self._finished: set[str] = set()

    def update(self, snapshots: list[MatchSnapshot]) -> list[MatchEvent]:
        events: list[MatchEvent] = []
        for snap in snapshots:
            if snap.event_id in self._finished:
                continue
            prev = self._last.get(snap.event_id)
            events.extend(self._diff(prev, snap))
            self._last[snap.event_id] = snap
            if snap.state == "post":
                self._finished.add(snap.event_id)
        return events

    def _diff(self, prev: MatchSnapshot | None, snap: MatchSnapshot) -> list[MatchEvent]:
        events: list[MatchEvent] = []
        if prev is None:
            if snap.state == "in":
                events.append(self._event("kickoff", snap))
            elif snap.state == "post":
                events.append(self._fulltime(snap))
            return events

        if prev.state == "pre" and snap.state in ("in", "post"):
            events.append(self._event("kickoff", snap))

        if snap.state in ("in", "post"):
            for _ in range(max(0, snap.our_score - prev.our_score)):
                events.append(self._event("goal_for", snap))
            for _ in range(max(0, snap.opp_score - prev.opp_score)):
                events.append(self._event("goal_against", snap))

        if prev.state != "post" and snap.state == "post":
            events.append(self._fulltime(snap))
        return events

    def _event(self, kind: str, snap: MatchSnapshot) -> MatchEvent:
        return MatchEvent(
            kind=kind,
            team_name=snap.team_name,
            opponent_name=snap.opponent_name,
            our_score=snap.our_score,
            opp_score=snap.opp_score,
        )

    def _fulltime(self, snap: MatchSnapshot) -> MatchEvent:
        if snap.our_score > snap.opp_score:
            result = "win"
        elif snap.our_score < snap.opp_score:
            result = "loss"
        else:
            result = "draw"
        return MatchEvent(
            kind="fulltime",
            team_name=snap.team_name,
            opponent_name=snap.opponent_name,
            our_score=snap.our_score,
            opp_score=snap.opp_score,
            result=result,
        )

    def has_live_match(self) -> bool:
        return any(
            s.state == "in" and s.event_id not in self._finished
            for s in self._last.values()
        )
