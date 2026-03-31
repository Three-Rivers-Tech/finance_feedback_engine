# Track 0 Learning-Chain Verification Runbook

## Quick check (< 2 minutes)

### 1. Backend healthy?
```bash
docker inspect ffe-backend --format "health={{if .State.Health}}{{.State.Health.Status}}{{end}} status={{.State.Status}}"
```

### 2. Recent adaptation activity?
```bash
docker logs --since 2h ffe-backend 2>&1 | grep -E "Adaptive weights evaluated|changed="
```

### 3. Collect proof packets
```bash
cat scripts/collect_proof_packet.py | docker exec -i ffe-backend python3 - --data-dir /app/data --last 3
```

## Verdict interpretation

| Verdict | Meaning | Action |
|---------|---------|--------|
| `pr4_proved` | Full chain: execution → outcome → learning → adaptation with provider-complete attribution | None needed |
| `lower_chain_only` | Learning chain works but adaptation not proved for this close (e.g. recovery provider, no ensemble attribution) | Expected for some closes; only concerning if *all* recent closes show this |
| `adaptive_starved` | Debate-mode decision persisted with judge-only `provider_decisions` (pre-fix artifact) | Expected for old artifacts; should not appear for decisions created after producer fix |
| `incomplete` | Missing artifacts (outcome file, decision file, or ensemble history) | Investigate — possible persistence failure |

## What to check if adaptation isn't firing

1. **Are there fresh closes?** Check trade outcomes:
   ```bash
   docker exec ffe-backend tail -n 5 /app/data/trade_outcomes/$(date -u +%Y-%m-%d).jsonl
   ```

2. **Is the learning handoff accepting?**
   ```bash
   docker logs --since 4h ffe-backend 2>&1 | grep "Learning handoff"
   ```

3. **Are new decision artifacts provider-complete?**
   ```bash
   docker exec ffe-backend sh -lc 'ls -lt /app/data/decisions/*.json | head -n 3'
   ```
   Then inspect: `provider_decisions` should have 3 keys in debate mode.

4. **Is ensemble history being written?**
   ```bash
   docker exec ffe-backend cat /app/data/decisions/ensemble_history.json
   ```

## Key file locations (inside container)

| Artifact | Path |
|----------|------|
| Decision artifacts | `/app/data/decisions/YYYY-MM-DD_<uuid>.json` |
| Outcome artifacts | `/app/data/memory/outcome_<uuid>.json` |
| Ensemble history | `/app/data/decisions/ensemble_history.json` |
| Trade outcomes | `/app/data/trade_outcomes/YYYY-MM-DD.jsonl` |
| Portfolio memory | `/app/data/memory/portfolio_memory.json` |

## Pass/fail criteria

### Lower chain (PR-1/2/3)
- ✅ Accepted close has learning handoff ACCEPTED
- ✅ Outcome artifact exists
- ✅ Decision artifact exists with lineage

### Adaptation (PR-4)
- ✅ `provider_decisions` has >1 key for debate-mode decisions
- ✅ `Adaptive weights evaluated` log line shows `changed=True`
- ✅ `ensemble_history.json` has entries for scored providers
- ✅ Proof packet collector returns `verdict: pr4_proved`
