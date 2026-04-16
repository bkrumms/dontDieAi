"""Battle simulator for Don't Die.

A pure, deterministic-given-a-seed battle engine that models:
- Dice rolling (uniform random per side)
- Damage, block, heal, poison, bleed, freeze, strength, armor
- Enemy attack patterns from Nick's database
- Scoring per Nick's Points sheet (per-roll, kill, low HP, speed, cumulative damage)

Use `dd_agent.sim.monte_carlo.run_trials` for distribution metrics, or call
`dd_agent.sim.battle.simulate_battle` directly for a single trial.
"""
