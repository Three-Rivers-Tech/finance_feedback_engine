**Context:** User experienced 404s from frontend because requests were hitting `http://localhost/api/api/...` (double /api). They explicitly asked to ensure this never regresses.

**Change (2026-01-02):** Normalized axios base URL in `frontend/src/api/client.ts` to strip trailing `/api` segments. Now `API_BASE_URL` ending with `/api` becomes host root, so paths like `/api/v1/...` no longer duplicate. Same behavior retained for normal host URLs (e.g., `http://localhost:8000`).

**Guardrail:** Do NOT remove this normalization; keep endpoints including `/api/v1/...` while base URL may or may not end with `/api`. If adjusting API base paths, re-run through this normalization or equivalent to avoid double-prefix bugs.