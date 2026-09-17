"""Choreographies for match reactions.

Every routine checks stop_event between steps so the app stops promptly.
"""

from __future__ import annotations

import threading

import numpy as np
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose


def _step(mini: ReachyMini, stop_event: threading.Event, duration: float, **kwargs) -> bool:
    """One goto_target step; returns False if we should abort."""
    if stop_event.is_set():
        return False
    mini.goto_target(duration=duration, **kwargs)
    return True


def _neutral(mini: ReachyMini, stop_event: threading.Event, duration: float = 1.0):
    _step(
        mini,
        stop_event,
        duration,
        head=create_head_pose(),
        antennas=np.deg2rad([0.0, 0.0]),
        body_yaw=0.0,
    )


def celebrate_goal(mini: ReachyMini, stop_event: threading.Event):
    """~8s of chaos: body spins, head pumps, antenna whips.

    Amplitudes stay inside the head's reachable workspace to avoid IK
    collision warnings (head z <= 8mm, rotations <= 15deg).
    """
    up = create_head_pose(z=8, pitch=-10, degrees=True, mm=True)
    for yaw in (55, -55):
        if not _step(
            mini, stop_event, 0.8,
            head=up,
            body_yaw=np.deg2rad(yaw),
            antennas=np.deg2rad([70, 70]),
            method="cartoon",
        ):
            return
    if not _step(mini, stop_event, 0.6, head=up, body_yaw=0.0, method="cartoon"):
        return
    for _ in range(3):
        if not _step(
            mini, stop_event, 0.35,
            head=create_head_pose(z=8, degrees=True, mm=True),
            antennas=np.deg2rad([70, 10]),
            method="cartoon",
        ):
            return
        if not _step(
            mini, stop_event, 0.35,
            head=create_head_pose(z=-3, roll=10, degrees=True, mm=True),
            antennas=np.deg2rad([10, 70]),
            method="cartoon",
        ):
            return
    _neutral(mini, stop_event)


def sad_slump(mini: ReachyMini, stop_event: threading.Event, hold: float = 3.0):
    """Head drops, antennas sag."""
    if not _step(
        mini, stop_event, 1.5,
        head=create_head_pose(z=-8, pitch=15, degrees=True, mm=True),
        antennas=np.deg2rad([-55, -55]),
        method="ease_in_out",
    ):
        return
    if stop_event.wait(hold):
        return
    _neutral(mini, stop_event, duration=2.0)


def perk_up(mini: ReachyMini, stop_event: threading.Event):
    """Kickoff: sit up, antennas alert, quick look left-right."""
    if not _step(
        mini, stop_event, 0.5,
        head=create_head_pose(z=8, degrees=True, mm=True),
        antennas=np.deg2rad([60, 60]),
        method="cartoon",
    ):
        return
    for yaw in (20, -20, 0):
        if not _step(
            mini, stop_event, 0.5,
            head=create_head_pose(z=6, yaw=yaw, degrees=True, mm=True),
        ):
            return
    _neutral(mini, stop_event)


def victory_dance(mini: ReachyMini, stop_event: threading.Event):
    """Full-time win: two celebration rounds."""
    celebrate_goal(mini, stop_event)
    if stop_event.is_set():
        return
    for roll in (15, -15, 15, -15):
        if not _step(
            mini, stop_event, 0.4,
            head=create_head_pose(z=8, roll=roll, degrees=True, mm=True),
            antennas=np.deg2rad([70, 70]),
            method="cartoon",
        ):
            return
    _neutral(mini, stop_event)


def defeat_slump(mini: ReachyMini, stop_event: threading.Event):
    sad_slump(mini, stop_event, hold=6.0)


def shrug(mini: ReachyMini, stop_event: threading.Event):
    """Full-time draw: ehh."""
    for roll in (15, -15):
        if not _step(
            mini, stop_event, 0.8,
            head=create_head_pose(roll=roll, degrees=True, mm=True),
            antennas=np.deg2rad([40, -20]),
        ):
            return
    _neutral(mini, stop_event)


def idle_targets(t: float, match_live: bool):
    """Low-amplitude breathing sway for the 50 Hz idle loop (set_target args)."""
    if match_live:
        z = 3.0 * np.sin(2 * np.pi * 0.25 * t)
        a = 12.0 + 6.0 * np.sin(2 * np.pi * 0.4 * t)
    else:
        z = 1.5 * np.sin(2 * np.pi * 0.12 * t)
        a = 4.0 * np.sin(2 * np.pi * 0.15 * t)
    return {
        "head": create_head_pose(z=z, degrees=True, mm=True),
        "antennas": np.deg2rad([a, a]),
    }
