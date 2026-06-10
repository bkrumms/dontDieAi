"""Bot-facing entry point for the autonomous run loop.

The actual implementation lives in `scripts/play_full_run.py` (4000+
lines of game-state-machine logic). This module is a thin import shim so
`bot/` doesn't reach into `scripts/`. It re-exports `play_full_run` and
the `RunStuck` sentinel exception.

Bot callers MUST pass `forfeit_on_exit=False`. Tournament NFTs cost real
money; the bot never auto-forfeits a stuck run. See
feedback_no_auto_forfeit.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the sibling `scripts/` dir importable.
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from play_full_run import (  # noqa: E402
    RunStuck,
    STUCK_END_REASONS,
    play_full_run,
)

__all__ = ["RunStuck", "STUCK_END_REASONS", "play_full_run"]
