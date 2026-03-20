# FFE Stage 51 — Adaptive Control Agent Lifecycle Control Contract Seam

## Why this stage exists

Stage 50 closed the **adaptive control config update transport contract** seam: a normalized, policy-selection-facing summary that adaptive-control-runtime-config-materialization artifacts can progress into authenticated `/config` update request/response behavior.

The next careful seam in the live repo is **adaptive control agent lifecycle control contract**.

This is the layer where authenticated control-plane behavior extends from config update into the operational agent-control endpoints that actually govern runtime execution state: start, stop, pause, resume, and status. It is narrower and more legible than jumping directly to broader health/readiness aggregation or deployment orchestration.

## Live repo evidence used for this draft

### Agent lifecycle control endpoints already exist
- `finance_feedback_engine/api/bot_control.py`
  - `@bot_control_router.post("/start", response_model=AgentStatusResponse)`
  - `@bot_control_router.post("/stop")`
  - `@bot_control_router.post("/pause", response_model=AgentStatusResponse)`
  - `@bot_control_router.post("/resume", response_model=AgentStatusResponse)`
  - `@bot_control_router.get("/status", response_model=AgentStatusResponse)`
  - `_api_user: str = Depends(verify_api_key_or_dev)` across the control surface
  - conflict / not-found / internal error shaping via `HTTPException` and `status.HTTP_*`

### Underlying runtime lifecycle state already exists
- `finance_feedback_engine/agent/trading_loop_agent.py`
  - `self.is_running = False`
  - `self._paused = False`
  - `self.stop_requested = False`
  - `def stop(self)`
  - `def pause(self) -> bool`
  - `def resume(self) -> bool`
  - warnings like:
    - `Cannot pause: agent is not running`
    - `Cannot pause: agent is already paused`
    - `Cannot resume: agent is not paused`

### Why this stands apart from broader health/deployment concerns
- separate health/readiness surface already exists outside this seam:
  - `finance_feedback_engine/api/routes.py`
  - `finance_feedback_engine/api/health_checks.py`
  - `get_enhanced_health_status(...)`
  - `get_readiness_status(...)`
- deployment/infra health is also separate:
  - `finance_feedback_engine/deployment/health.py`

## Why this is the next honest seam

The live repo still separates at least three nearby concerns:
1. authenticated config update transport (`PATCH /config`) — now covered by Stage 50
2. authenticated agent lifecycle control contract (`/start`, `/stop`, `/pause`, `/resume`, `/status`)
3. broader health/readiness/deployment status aggregation and rollout observability

Stage 51 should cover the second.
A later stage can decide whether health/readiness aggregation or deployment-state reporting deserves its own seam.

## Stage 51 scope

### Build from
- Stage 50 adaptive-control-config-update-transport-contract summaries
- live repo evidence around agent lifecycle control behavior:
  - start/stop/pause/resume/status endpoint contracts
  - authenticated dependency usage
  - conflict / unavailable / internal error shaping
  - explicit running/paused lifecycle state in the trading loop agent

### Stage 51 should preserve as policy-facing signals
- how many comparable adaptive-control-config-update-transport-contract artifacts progressed into lifecycle-control-contract-ready updates
- how many remained shadow / primary-cutover / manual-hold / deferred shaped
- that start/stop/pause/resume/status-facing control outcomes remain exportable and persistence-verifiable without collapsing into a vague “ops happened” blob

## Still explicitly NOT this stage
- health/readiness aggregate payloads
- deployment liveness probes or infra-level health checks
- websocket/dashboard/SSE fanout
- external process supervisor semantics
- cross-host rollout coordination
- manual-trade execution behavior
- Thompson posterior math
- Kelly sizing internals

## Careful seam definition

### adaptive-control-agent-lifecycle-control-contract-ready
A normalized policy-selection layer that says:
- adaptive-control-config-update-transport-contract artifacts were eligible to progress into authenticated agent lifecycle control behavior
- lifecycle-control outcomes remain representable in an auditable request/response-style contract
- running / paused / stopped pathway distinctions remain visible as structured control summaries

It does **not** yet promise health aggregation correctness, cross-process orchestration, or deployment-wide observability guarantees.

## Why not jump straight to health/readiness
The repo already shows health/readiness as a broader surface spanning separate modules and aggregated status composition. The lifecycle control surface is a tighter next seam because it sits immediately adjacent to the authenticated bot control endpoints already driving Stage 50’s transport contract.

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_adaptive_control_agent_lifecycle_control_contract_set(...)`
2. **PR-2** — `build_policy_selection_adaptive_control_agent_lifecycle_control_contract_summary(...)`
3. **PR-3** — end-to-end adaptive-control-agent-lifecycle-control-contract chain hardening
4. **PR-4** — `extract_policy_selection_adaptive_control_agent_lifecycle_control_contract_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
We are still following the same seam discipline used across the prior stages:
- derive from live repo evidence, not stale intention alone
- keep one narrow abstraction layer at a time
- prefer policy-facing summaries before broader operational aggregation
- keep the system auditable, understandable, and re-derivable later

## Documentation cohesion note
Keep the seam trail in `docs/plans/` instead of bloating root docs with migration-by-migration detail.
