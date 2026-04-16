"""Minimal live viewer — WebSocket state stream + one HTML page.

Mount-point: /viewer/{session_id}
WebSocket:   /ws/{session_id}

Subscribes to the in-memory bus topic `run:{session_id}:state` and pushes
each update to the connected browser as JSON.
"""
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from dd_agent.bus import bus


app = FastAPI()


VIEWER_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Don't Die — Agent Viewer</title>
<style>
  body { font-family: ui-monospace, monospace; background: #0b0b0b; color: #e8e8e8; padding: 24px; margin: 0; }
  h1 { color: #ff5a5a; margin: 0 0 8px 0; }
  .meta { color: #888; margin-bottom: 16px; }
  pre { background: #000; padding: 14px; border: 1px solid #222; border-radius: 6px; overflow-x: auto; }
  .status { color: #5f5; }
  .disc { color: #f55; }
</style></head><body>
  <h1>Don't Die — Agent Viewer</h1>
  <div class="meta">session <code id="sid"></code> · <span id="status" class="status">connecting…</span></div>
  <pre id="state">waiting for state…</pre>
<script>
  const sid = location.pathname.split('/').pop();
  document.getElementById('sid').textContent = sid;
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${scheme}://${location.host}/ws/${sid}`);
  const status = document.getElementById('status');
  const state = document.getElementById('state');
  ws.onopen = () => { status.textContent = 'live'; };
  ws.onmessage = e => { state.textContent = e.data; };
  ws.onclose = () => { status.textContent = 'disconnected'; status.className = 'disc'; };
</script>
</body></html>
"""


@app.get("/viewer/{session_id}", response_class=HTMLResponse)
async def viewer(session_id: str):
    return VIEWER_HTML


@app.websocket("/ws/{session_id}")
async def ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    q = bus.subscribe(f"run:{session_id}:state")
    try:
        while True:
            state = await q.get()
            await websocket.send_text(json.dumps(state, default=str, indent=2))
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(f"run:{session_id}:state", q)
