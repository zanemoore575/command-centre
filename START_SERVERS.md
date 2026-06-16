# Starting the CAiS Servers

Three terminals, run them in order. Each command below is ready to paste as-is.

---

## Terminal 1 — MCP Server (port 8001)

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend" && source venv/bin/activate && python -m app.mcp.server
```

**Ready when you see:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001
```

---

## Terminal 2 — ngrok Tunnel

```bash
ngrok http 8001 --url=rufous-aracely-unimpedingly.ngrok-free.dev
```

**Ready when you see:**
```
Forwarding  https://rufous-aracely-unimpedingly.ngrok-free.dev -> http://localhost:8001
```

---

## Terminal 3 — FastAPI Backend (only needed if using the web UI)

Not required for Claude.ai — skip this unless you want the local web interface.

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend" && source venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

## Reconnecting Claude.ai after a restart

1. Start Terminal 1 (MCP server) — wait for `Application startup complete`
2. Start Terminal 2 (ngrok) — wait for the `Forwarding` line
3. Go to claude.ai → Settings → Integrations
4. Remove the existing CAiS connector
5. Add it back with URL: `https://rufous-aracely-unimpedingly.ngrok-free.dev/mcp`
6. Sign in with Google when prompted

---

## If port 8001 is already in use

```bash
lsof -ti :8001 | xargs kill -9
```

Then restart Terminal 1.

---

## Quick health check (run in any terminal)

Confirms the MCP server is up and serving the right tools:

```bash
curl -s http://127.0.0.1:8001/mcp \
  -H "Authorization: Bearer local-dev-only-token" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python3 -m json.tool
```

You should see `discover_database`, `get_recent_memories`, `search_memories`, etc. in the output.
