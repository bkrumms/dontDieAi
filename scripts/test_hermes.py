#!/usr/bin/env python3
"""Quick test: call Hermes directly and print raw response."""
import httpx, json

payload = {
    "model": "hermes3",
    "messages": [
        {
            "role": "system",
            "content": 'You are a Don\'t Die pick advisor. Respond ONLY in JSON: {"pick_index": <int>, "rationale": "<reason>"}.',
        },
        {
            "role": "user",
            "content": (
                "TARGET DIE: 3  role: defense — Block/Armor only, non-exhaust attacks are run-killers\n\n"
                "OFFERED SIDES:\n"
                "  [0] Block 12  tier=Level 3\n"
                "  [1] Attack 14, Gain 5 Strength  tier=Level 3\n"
                "  [2] Cursed Weakness  tier=Curse\n\n"
                "Choose the best pick. JSON only."
            ),
        },
    ],
    "temperature": 0.1,
    "max_tokens": 200,
}

print("Calling Hermes (may take 60-90s on CPU)...")
resp = httpx.post("http://localhost:11434/v1/chat/completions", json=payload, timeout=120.0)
print("Status:", resp.status_code)
data = resp.json()
content = data["choices"][0]["message"]["content"]
print("Raw response:", repr(content))
try:
    parsed = json.loads(content)
    print("Parsed:", parsed)
except Exception as e:
    print("JSON parse error:", e)
