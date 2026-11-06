# Troubleshooting

Common failures observed while running Fixture, with one fix each.

---

## 1. Port conflict on `:8766`

**Symptom:** The harness fails to start with
`ERROR: [Errno 98] Address already in use` (Linux/macOS) or
`[WinError 10048]` / "Only one usage of each socket address" (Windows) when
binding `:8766`.

**Cause:** Another process already holds the port.

**Fix:** Set the `FIXTURE_PORT` environment variable to a free port and
restart the harness.

---

## 2. Ollama not responding

**Symptom:** `GET /health` returns `ollama: false`.

**Cause:** The Ollama server is not running or is not reachable on its port.

**Fix:** Verify Ollama is running on `:11434` (start it, or pull/confirm the
configured model) and re-check `/health`.

---

## 3. Quantity serialization errors in FreeCAD chat (fixed)

**Status:** Fixed in the current client; kept for anyone running an older copy.

**Symptom (historical):** Quantity serialization errors surfaced while chatting
in FreeCAD.

**Cause:** The client did not normalize FreeCAD `Units.Quantity` values before
JSON serialization.

**Fix:** Update the client, then restart it (a running session keeps the stale
behavior until restarted).

---

## 4. FreeCAD GUI freeze (fixed)

**Status:** Fixed in the current client; kept for anyone running an older copy.

**Symptom (historical):** The FreeCAD GUI froze during chat or selection
operations.

**Cause:** HTTP work ran on the GUI thread instead of a worker thread.

**Fix:** Update the client, which moves the HTTP call onto a worker thread
(`QThread`) rather than blocking the GUI thread.

---

## 5. Model ignores tools

**Symptom:** The model does not call the expected tools.

**Cause:** The prompt/model output is not constrained to the tool-calling
format.

**Fix:** Use `format: json`, post-filter the response, and provide clear system
rules describing the tools.
