from goal_screamer.scores import MatchSnapshot, MatchTracker, parse_matches


def snap(state="pre", ours=0, theirs=0, event_id="e1"):
    return MatchSnapshot(
        event_id=event_id,
        team_id="21812",
        team_name="St. Louis CITY SC",
        opponent_name="Sporting KC",
        our_score=ours,
        opp_score=theirs,
        state=state,
    )


def kinds(events):
    return [e.kind for e in events]


def test_full_match_flow():
    tracker = MatchTracker()
    assert tracker.update([snap("pre")]) == []
    assert kinds(tracker.update([snap("in")])) == ["kickoff"]
    assert kinds(tracker.update([snap("in", ours=1)])) == ["goal_for"]
    assert kinds(tracker.update([snap("in", ours=1, theirs=1)])) == ["goal_against"]
    assert kinds(tracker.update([snap("in", ours=2, theirs=1)])) == ["goal_for"]
    final = tracker.update([snap("post", ours=2, theirs=1)])
    assert kinds(final) == ["fulltime"]
    assert final[0].result == "win"


def test_two_goals_between_polls():
    tracker = MatchTracker()
    tracker.update([snap("in")])
    assert kinds(tracker.update([snap("in", ours=2)])) == ["goal_for", "goal_for"]


def test_app_started_mid_match_sets_baseline_without_goal_events():
    tracker = MatchTracker()
    events = tracker.update([snap("in", ours=2, theirs=1)])
    assert kinds(events) == ["kickoff"]
    assert kinds(tracker.update([snap("in", ours=3, theirs=1)])) == ["goal_for"]


def test_missed_kickoff_pre_straight_to_post():
    tracker = MatchTracker()
    tracker.update([snap("pre")])
    events = tracker.update([snap("post", ours=1, theirs=1)])
    assert kinds(events) == ["kickoff", "goal_for", "goal_against", "fulltime"]
    assert events[-1].result == "draw"


def test_finished_match_never_replays():
    tracker = MatchTracker()
    tracker.update([snap("post", ours=0, theirs=3)])
    assert tracker.update([snap("post", ours=0, theirs=3)]) == []


def test_loss_result():
    tracker = MatchTracker()
    tracker.update([snap("in")])
    events = tracker.update([snap("post", theirs=1)])
    assert [e.kind for e in events] == ["goal_against", "fulltime"]
    assert events[-1].result == "loss"


def test_has_live_match():
    tracker = MatchTracker()
    assert not tracker.has_live_match()
    tracker.update([snap("in")])
    assert tracker.has_live_match()
    tracker.update([snap("post")])
    assert not tracker.has_live_match()


def test_parse_matches_espn_shape():
    scoreboard = {
        "events": [
            {
                "id": "401234",
                "status": {"type": {"state": "in"}},
                "competitions": [
                    {
                        "competitors": [
                            {
                                "team": {"id": "21812", "displayName": "St. Louis CITY SC"},
                                "score": "1",
                                "homeAway": "home",
                            },
                            {
                                "team": {"id": "186", "displayName": "Sporting Kansas City"},
                                "score": "0",
                                "homeAway": "away",
                            },
                        ]
                    }
                ],
            },
            {
                "id": "401235",
                "status": {"type": {"state": "pre"}},
                "competitions": [
                    {
                        "competitors": [
                            {"team": {"id": "1", "displayName": "A"}, "score": "0"},
                            {"team": {"id": "2", "displayName": "B"}, "score": "0"},
                        ]
                    }
                ],
            },
        ]
    }
    snaps = parse_matches(scoreboard, {"21812": "St. Louis CITY SC"})
    assert len(snaps) == 1
    s = snaps[0]
    assert s.event_id == "401234"
    assert s.our_score == 1 and s.opp_score == 0
    assert s.opponent_name == "Sporting Kansas City"
    assert s.state == "in"
