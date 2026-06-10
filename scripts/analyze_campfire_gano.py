import io, sys, re
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logfile = r"C:\Users\bekru\AppData\Local\Temp\claude\C--dev-dontDieAi\c501ee04-4cd0-4045-859f-25e4cf196765\tasks\bo7icwxs2.output"

with open(logfile, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Parse runs
runs = []
current_run = None

for i, line in enumerate(lines):
    m = re.match(r'>>> run #(\d+)', line)
    if m:
        if current_run:
            runs.append(current_run)
        current_run = {
            'num': int(m.group(1)),
            'campfires': [],
            'gano_found': False,
            'gano_result': None,
            'gano_hp_before': None,
            'gano_hp_after': None,
            'gano_food': [],
            'gano_line': -1,
            '_last_pos': '?',
            '_last_hp': 0,
            '_last_max_hp': 0,
            '_last_sim': None,
            '_current_battle_monsters': None,
        }
        continue

    if not current_run:
        continue

    # State line with pos and hp
    m = re.search(r'state=(\w+)\s+pos=([\w\[\]]+)\s+hp=(\d+)/(\d+)', line)
    if m:
        current_run['_last_pos'] = m.group(2)
        current_run['_last_hp'] = int(m.group(3))
        current_run['_last_max_hp'] = int(m.group(4))

    # Campfire sim
    m = re.search(r'campfire sim options: (.+)', line)
    if m:
        current_run['_last_sim'] = m.group(1).strip()

    # Campfire decision
    m = re.search(r'campfire decision \(([^)]+)\): (\S+)(.*)', line)
    if m:
        pos = current_run['_last_pos']
        hp = current_run['_last_hp']
        max_hp = current_run['_last_max_hp']
        sim = current_run.pop('_last_sim', None)
        current_run['_last_sim'] = None
        decision = m.group(2)
        reason = m.group(3).strip()
        current_run['campfires'].append({
            'pos': pos,
            'hp': hp,
            'max_hp': max_hp,
            'decision': decision,
            'reason': reason,
            'sim': sim,
            'line': i,
        })

    # Battle start with monsters
    m = re.search(r'monsters: (.+)', line)
    if m:
        monsters = m.group(1).strip()
        current_run['_current_battle_monsters'] = monsters
        if 'Ganondwarf' in monsters:
            current_run['gano_found'] = True
            current_run['gano_line'] = i
            current_run['gano_hp_before'] = current_run['_last_hp']
            current_run['gano_max_hp'] = current_run['_last_max_hp']

    # Pre-fight food near Ganondwarf (two patterns: normal pre-fight and hail-mary dump)
    food_match = re.search(r'(?:pre-fight food: activating|activating) (.+?)(?:\s*→.*)?$', line)
    if food_match:
        food = food_match.group(1).strip()
        if current_run['gano_found'] and current_run['gano_result'] is None:
            if food not in current_run['gano_food']:
                current_run['gano_food'].append(food)

    # Battle result
    m = re.search(r'battle result: (won|lost)', line)
    if m:
        result = m.group(1)
        if current_run['gano_found'] and current_run['gano_result'] is None:
            if current_run.get('_current_battle_monsters') and 'Ganondwarf' in current_run['_current_battle_monsters']:
                current_run['gano_result'] = result
                for j in range(max(0, i - 20), i):
                    pm = re.search(r'outcome=\w+ playerHP=(\d+)', lines[j])
                    if pm:
                        current_run['gano_hp_after'] = int(pm.group(1))
        current_run['_current_battle_monsters'] = None

if current_run:
    runs.append(current_run)

# Also scan for food lines right before Ganondwarf monsters line
for run in runs:
    if not run['gano_found']:
        continue
    gano_line = run['gano_line']
    for j in range(max(0, gano_line - 15), gano_line):
        m = re.search(r'pre-fight food: activating (.+)', lines[j])
        if m:
            food = m.group(1).strip()
            if food not in run['gano_food']:
                run['gano_food'].append(food)

# Print table
print("=" * 180)
print(f"{'Run#':>4} | {'Gano':>6} | {'Last CF Decision':>25} | {'CF Pos':>10} | {'HP@CF':>8} | {'HP@Gano':>9} | {'HP After':>8} | {'Food Used':>30} | Campfire Sim Results")
print("-" * 180)

gano_runs = []
for run in runs:
    if not run['gano_found']:
        continue

    last_cf = None
    for cf in run['campfires']:
        if cf['line'] < run['gano_line']:
            last_cf = cf

    cf_decision = last_cf['decision'] if last_cf else 'none'
    cf_hp = f"{last_cf['hp']}/{last_cf['max_hp']}" if last_cf else '-'
    cf_sim = last_cf['sim'] if last_cf and last_cf['sim'] else '-'
    cf_pos = last_cf['pos'] if last_cf else '-'
    gano_hp = f"{run['gano_hp_before']}/{run.get('gano_max_hp', '?')}"
    hp_after = str(run['gano_hp_after']) if run['gano_hp_after'] else '-'
    food = ', '.join(run['gano_food']) if run['gano_food'] else 'none'
    result = run['gano_result'] or '?'

    gano_runs.append({
        'num': run['num'],
        'result': result,
        'cf_decision': cf_decision,
        'cf_hp': cf_hp,
        'cf_pos': cf_pos,
        'gano_hp_before': run['gano_hp_before'],
        'gano_max_hp': run.get('gano_max_hp', '?'),
        'hp_after': run['gano_hp_after'],
        'food': food,
        'cf_sim': cf_sim,
    })

    print(f"{run['num']:>4} | {result:>6} | {cf_decision:>25} | {cf_pos:>10} | {cf_hp:>8} | {gano_hp:>9} | {hp_after:>8} | {food:>30} | {cf_sim}")

print("=" * 180)

wins = [r for r in gano_runs if r['result'] == 'won']
losses = [r for r in gano_runs if r['result'] == 'lost']

print(f"\nTotal runs reaching Ganondwarf: {len(gano_runs)}")
print(f"Wins: {len(wins)}, Losses: {len(losses)}")


def decision_breakdown(group, label):
    if not group:
        return
    burns = sum(1 for r in group if 'burn' in r['cf_decision'])
    rests = sum(1 for r in group if 'rest' in r['cf_decision'])
    foods = sum(1 for r in group if 'boost' in r['cf_decision'] or 'food' in r['cf_decision'])
    nones = sum(1 for r in group if r['cf_decision'] == 'none')
    total = len(group)
    print(f"\n{label} (n={total}):")
    print(f"  Burn:  {burns} ({100 * burns / total:.0f}%)")
    print(f"  Rest:  {rests} ({100 * rests / total:.0f}%)")
    print(f"  Food:  {foods} ({100 * foods / total:.0f}%)")
    if nones:
        print(f"  None:  {nones} ({100 * nones / total:.0f}%)")


decision_breakdown(wins, "Ganondwarf WINS - last campfire decision")
decision_breakdown(losses, "Ganondwarf LOSSES - last campfire decision")

if wins:
    valid = [r['gano_hp_before'] for r in wins if isinstance(r['gano_hp_before'], int)]
    if valid:
        print(f"\nAvg HP going into Ganondwarf (wins):   {sum(valid) / len(valid):.1f}")
if losses:
    valid = [r['gano_hp_before'] for r in losses if isinstance(r['gano_hp_before'], int)]
    if valid:
        print(f"Avg HP going into Ganondwarf (losses): {sum(valid) / len(valid):.1f}")

if wins:
    valid_hp_after = [r['hp_after'] for r in wins if r['hp_after'] is not None]
    if valid_hp_after:
        print(f"Avg HP after beating Ganondwarf:        {sum(valid_hp_after) / len(valid_hp_after):.1f}")

ice_rice_count = sum(1 for r in gano_runs if 'Ice Rice' in r['food'])
print(f"\nRuns with Ice Rice for Ganondwarf: {ice_rice_count}/{len(gano_runs)} ({100 * ice_rice_count / len(gano_runs):.0f}%)")
ice_rice_wins = sum(1 for r in wins if 'Ice Rice' in r['food'])
ice_rice_losses = sum(1 for r in losses if 'Ice Rice' in r['food'])
if wins:
    print(f"  Wins with Ice Rice:   {ice_rice_wins}/{len(wins)}")
if losses:
    print(f"  Losses with Ice Rice: {ice_rice_losses}/{len(losses)}")

print("\nAll foods used against Ganondwarf:")
food_counter = Counter()
for r in gano_runs:
    for f in r['food'].split(', '):
        if f.strip() != 'none':
            food_counter[f.strip()] += 1
for food, count in food_counter.most_common():
    print(f"  {food}: {count}")

print("\n--- Last campfire sim results before Ganondwarf (when sim ran) ---")
for r in gano_runs:
    if r['cf_sim'] != '-':
        print(f"  Run #{r['num']:>2} ({r['result']:>4}): decision={r['cf_decision']:<15} sim={r['cf_sim']}")

# Additional: how far was last campfire from Ganondwarf?
print("\n--- Last campfire position before Ganondwarf ---")
pos_counter = Counter()
for r in gano_runs:
    pos_counter[r['cf_pos']] += 1
for pos, count in pos_counter.most_common():
    print(f"  {pos}: {count} runs")
