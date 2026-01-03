Added guards against undefined status strings before calling toUpperCase to prevent runtime TypeError seen in production bundle.
- Header now uses statusLabel with fallback 'UNKNOWN' when health.status is missing.
- AgentStatusDisplay now uppercases status.state with fallback 'unknown'.
Files: frontend/src/components/layout/Header.tsx, frontend/src/components/agent/AgentStatusDisplay.tsx.