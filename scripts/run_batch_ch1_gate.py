"""Run up to N full runs, stopping early if any run dies in Ch1 (never reaches Ganondwarf)."""
import sys, asyncio, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.play_full_run import main as pfr_main

async def run_batch(n_runs):
    from datetime import datetime
    from dd_agent.dd_client import DDClient

    dd = DDClient()
    try:
        chars = await dd._get("/api/characters/solo")
        character_id = chars if isinstance(chars, str) else (chars or {}).get("id")
        if not character_id:
            print("could not determine character_id")
            return
        print(f"character_id: {character_id}")

        from scripts.play_full_run import play_full_run, RunLogger
        for i in range(1, n_runs + 1):
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            out_dir = Path("data/full_runs") / f"{stamp}_r{i}"
            print(f"\n>>> run #{i} logging to {out_dir}")
            await play_full_run(dd, character_id, out_dir)

            # Check if run made it past Ch1 by reading the summary
            logger_path = out_dir / "_summary.json"
            import json
            summary = {}
            if logger_path.exists():
                with open(logger_path) as f:
                    summary = json.load(f)

            battles = summary.get("battles", [])
            beat_ganondwarf = any(
                b.get("result") == "won" and any(
                    "Ganondwarf" in (m.get("name", "") if isinstance(m, dict) else str(m))
                    for m in (b.get("monsters") or [])
                )
                for b in battles
            )
            end_reason = summary.get("end_reason", "")

            if end_reason in ("battle_lost", "stuck") and not beat_ganondwarf:
                print(f"\n!!! RUN #{i} DIED IN CH1 — stopping batch !!!")
                break

            if i < n_runs:
                await asyncio.sleep(15)
    finally:
        await dd.close()

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    asyncio.run(run_batch(n))
