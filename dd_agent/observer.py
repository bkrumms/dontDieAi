"""Passive run observer.

Consumes merged state dicts (combining /api/character + /api/game responses)
and emits structured events whenever anything interesting changes between
polls. Writes two files:

  data/runs/<session_id>/states.jsonl  — every poll's raw merged state
  data/runs/<session_id>/events.md     — human-readable event timeline

The observer never calls POST endpoints.

## Merged state shape (what the watcher builds and feeds us)

Top-level flat keys (nullable if the endpoint wasn't polled yet):

- `health`, `max_health`, `gold`, `points` (int), `time_crystal`
- `dices[]`, `boosts[]`, `trinkets[]`
- `characterId`, `lootMul`, `lootPoints`, `nftType`
- `inState`, `activePath`, `currentIndex`, `rolledSteps`, `checkpointPending`
- `chapter`, `nextRerollCost`, `upcoming_boss`, `isTournament`
"""
import json
from datetime import datetime
from pathlib import Path


TERMINAL_STATES = {"dead", "ended", "forfeited", "won", "win", "lose", "lost"}


def _int(x, default: int = 0) -> int:
    """Coerce points and similar string-or-int fields to int."""
    if x is None:
        return default
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


class Observer:
    def __init__(self, session_id: str, states_path: Path, events_path: Path):
        self.session_id = session_id
        self.states_path = states_path
        self.events_path = events_path
        self._states_fh = states_path.open("a", encoding="utf-8")
        self._events_fh = events_path.open("a", encoding="utf-8")

        self._prev: dict | None = None
        self._terminal = False
        self.poll_count = 0
        self.event_count = 0

        header = f"\n## Watch session started {datetime.utcnow().isoformat()}Z — `{session_id}`\n\n"
        self._events_fh.write(header)
        self._events_fh.flush()

    def is_terminal(self) -> bool:
        return self._terminal

    def close(self):
        try:
            self._states_fh.close()
        finally:
            self._events_fh.close()

    # ------------------------------------------------------------------
    def record(self, state: dict | None) -> list[str]:
        """Log the poll and return any new events as strings."""
        self.poll_count += 1
        now = datetime.utcnow().isoformat()

        self._states_fh.write(json.dumps({"ts": now, "state": state}, default=str) + "\n")
        self._states_fh.flush()

        events: list[str] = []
        if self._prev is None:
            events.append(self._fmt("INIT", self._summary(state or {})))
        else:
            events.extend(self._diff_events(self._prev, state or {}))

        self._prev = state or {}

        in_state = (state or {}).get("inState") or ""
        if in_state in TERMINAL_STATES and not self._terminal:
            self._terminal = True
            events.append(self._fmt("TERMINAL", f"state=`{in_state}`"))

        for e in events:
            self._events_fh.write(e + "\n")
            self.event_count += 1
        if events:
            self._events_fh.flush()

        return events

    # ------------------------------------------------------------------
    def _fmt(self, tag: str, body: str) -> str:
        ts = datetime.utcnow().strftime("%H:%M:%S")
        return f"- `{ts}` **{tag}** — {body}"

    def _summary(self, s: dict) -> str:
        return (
            f"inState=`{s.get('inState')}` "
            f"HP={s.get('health')}/{s.get('max_health')} "
            f"TC={s.get('time_crystal')} "
            f"gold={s.get('gold')} "
            f"points={_int(s.get('points'))} "
            f"path=`{s.get('activePath')}`[{s.get('currentIndex')}] "
            f"chapter={s.get('chapter')}"
        )

    def _diff_events(self, prev: dict, curr: dict) -> list[str]:
        out: list[str] = []

        def pair(k):
            return curr.get(k), prev.get(k)

        ci, pi = pair("inState")
        if ci != pi:
            out.append(self._fmt("STATE", f"`{pi}` -> `{ci}`"))

        ch, ph = pair("health")
        if ch is not None and ph is not None and ch != ph:
            delta = ch - ph
            tag = "HEAL" if delta > 0 else "DAMAGE"
            out.append(self._fmt(tag, f"{ph} -> {ch} ({delta:+d})"))

        # max_health can change from trinkets / curses
        cmh, pmh = pair("max_health")
        if cmh is not None and pmh is not None and cmh != pmh:
            out.append(self._fmt("MAX-HP", f"{pmh} -> {cmh} ({cmh - pmh:+d})"))

        ctc, ptc = pair("time_crystal")
        if ctc is not None and ptc is not None and ctc != ptc:
            delta = ctc - ptc
            out.append(self._fmt("TC", f"{ptc} -> {ctc} ({delta:+d})"))

        cg, pg = pair("gold")
        if cg is not None and pg is not None and cg != pg:
            delta = cg - pg
            out.append(self._fmt("GOLD", f"{pg} -> {cg} ({delta:+d})"))

        cpt, ppt = _int(curr.get("points")), _int(prev.get("points"))
        if cpt != ppt:
            out.append(self._fmt("POINTS", f"{ppt} -> {cpt} ({cpt - ppt:+d})"))

        ca, pa = pair("activePath")
        cidx, pidx = pair("currentIndex")
        if (ca, cidx) != (pa, pidx):
            out.append(self._fmt("MOVE", f"`{pa}`[{pidx}] -> `{ca}`[{cidx}]"))

        crs, prs = pair("rolledSteps")
        if crs != prs and crs is not None:
            out.append(self._fmt("ROLL", f"rolled {crs}"))

        ccp, pcp = pair("checkpointPending")
        if ccp != pcp:
            out.append(self._fmt("CHECKPOINT", f"pending {pcp} -> {ccp}"))

        cch, pch = pair("chapter")
        if cch != pch:
            out.append(self._fmt("CHAPTER", f"{pch} -> {cch}"))

        # dice ability changes — detects upgrades, burns, curses applied
        cd = curr.get("dices") or []
        pd = prev.get("dices") or []
        for i in range(max(len(cd), len(pd))):
            cdie = cd[i] if i < len(cd) else {}
            pdie = pd[i] if i < len(pd) else {}
            cab = self._ability_labels(cdie)
            pab = self._ability_labels(pdie)
            if cab != pab:
                added = [x for x in cab if x not in pab]
                removed = [x for x in pab if x not in cab]
                parts = []
                if added:
                    parts.append(f"+{added}")
                if removed:
                    parts.append(f"-{removed}")
                out.append(self._fmt("DIE", f"die#{i + 1}: {' '.join(parts)}"))

        # trinkets
        ct = self._names(curr.get("trinkets") or [])
        pt = self._names(prev.get("trinkets") or [])
        added_t = [x for x in ct if x not in pt]
        removed_t = [x for x in pt if x not in ct]
        if added_t:
            out.append(self._fmt("TRINKET+", ", ".join(added_t)))
        if removed_t:
            out.append(self._fmt("TRINKET-", ", ".join(removed_t)))

        # boosts (food)
        cb = self._names(curr.get("boosts") or [])
        pb = self._names(prev.get("boosts") or [])
        added_b = [x for x in cb if x not in pb]
        removed_b = [x for x in pb if x not in cb]
        if added_b:
            out.append(self._fmt("FOOD+", ", ".join(added_b)))
        if removed_b:
            out.append(self._fmt("FOOD-", ", ".join(removed_b)))

        # loot multiple
        cl, pl = pair("lootMul")
        if cl != pl and cl is not None:
            out.append(self._fmt("LOOT-MUL", f"{pl} -> {cl}"))
        clp, plp = pair("lootPoints")
        if clp != plp and clp is not None:
            out.append(self._fmt("LOOT-PTS", f"{plp} -> {clp}"))

        # next reroll cost changing signals TC budget pressure
        cnrc, pnrc = pair("nextRerollCost")
        if cnrc != pnrc and cnrc is not None:
            out.append(self._fmt("REROLL-COST", f"{pnrc} -> {cnrc}"))

        return out

    def _ability_labels(self, die: dict) -> list[str]:
        return [
            a.get("label") or str(a.get("id") or "?")
            for a in (die.get("ability") or [])
        ]

    def _names(self, items: list) -> list[str]:
        # Food uses `type`, trinkets use `label`, others may use `name`/`id`.
        return [
            (i.get("name") or i.get("label") or i.get("type") or str(i.get("id") or "?"))
            for i in items
            if isinstance(i, dict)
        ]
