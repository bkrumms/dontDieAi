import json
import os

from dotenv import load_dotenv

load_dotenv()

DD_API_BASE = os.getenv("DD_API_BASE", "https://dd-api-dev.anomalygames.ai")

# auth — pick whichever the dev build uses, or combine
DD_AUTH_TOKEN = os.getenv("DD_AUTH_TOKEN", "")
DD_COOKIE = os.getenv("DD_COOKIE", "")
_extra_raw = os.getenv("DD_EXTRA_HEADERS", "")
try:
    DD_EXTRA_HEADERS: dict = json.loads(_extra_raw) if _extra_raw else {}
except json.JSONDecodeError:
    print("[config] DD_EXTRA_HEADERS is not valid JSON, ignoring")
    DD_EXTRA_HEADERS = {}

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

# Hermes shadow observer — set HERMES_ENABLED=true to activate
HERMES_ENABLED = os.getenv("HERMES_ENABLED", "false").lower() == "true"
HERMES_BASE_URL = os.getenv("HERMES_BASE_URL", "http://localhost:11434/v1")  # Ollama default
HERMES_MODEL = os.getenv("HERMES_MODEL", "hermes3")

WEB_BASE_URL = os.getenv("WEB_BASE_URL", "http://localhost:8000")

# Discord-bot persistence + secrets (see dd_agent/store.py, dd_agent/secrets.py)
DD_BOT_DB_PATH = os.getenv("DD_BOT_DB_PATH", "./bot_state.db")
DD_BOT_SECRET_KEY = os.getenv("DD_BOT_SECRET_KEY", "")

if not DD_BOT_SECRET_KEY:
    print(
        "[config] DD_BOT_SECRET_KEY is not set — bot will fail to encrypt user JWTs. "
        "Generate one with `python -m dd_agent.secrets` and add to .env."
    )
