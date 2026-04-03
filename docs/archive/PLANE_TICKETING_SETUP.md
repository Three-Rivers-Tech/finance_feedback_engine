# Plane Ticketing System Integration

**Status:** ✅ READY TO USE (2026-02-19 22:45 ET)

FFE now has full integration with the Plane ticketing system running at `http://192.168.1.177:8088`.

---

## What's Been Configured

### 1. Environment Variables (n8n)
The n8n container on `business-tools` (192.168.1.197:5678) now has these env vars:

```bash
PLANE_API_KEY=${PLANE_API_KEY}
PLANE_API_BASE=http://192.168.1.177:8088
PLANE_WORKSPACE_SLUG=grovex-tech-solutions
PLANE_PROJECT_ID=a751111c-fa00-4004-b725-d1174e488fe0
```

These are already set in `/opt/business-tools/.env` on the LXC and passed to the n8n Docker container.

### 2. FFE Python Client
New module: `ffe_plane_client.py` in the FFE repo root provides:
- `PlaneClient` class for full API access
- `create_execution_ticket()` - log trade executions
- `create_risk_ticket()` - log risk blocks
- Full CRUD operations for issues

### 3. Working Examples
See `examples/plane_ticketing_example.py` for:
- Creating execution tickets (successful/failed trades)
- Creating risk block tickets
- Listing FFE issues
- Adding comments
- Advanced API usage

---

## Quick Start

### Test the Integration

```bash
cd ~/finance_feedback_engine

# Set API key
export PLANE_API_KEY='${PLANE_API_KEY}'

# List existing FFE issues
python3 examples/plane_ticketing_example.py

# Create test tickets (uncomment examples in the script first)
# Then run again
```

### Use in FFE Code

```python
from ffe_plane_client import create_execution_ticket, create_risk_ticket

# After trade execution
issue_id = create_execution_ticket(
    decision_id=decision.id,
    symbol="BTC/USD",
    direction="LONG",
    confidence=0.85,
    error=None  # or error message if failed
)

# When risk blocks a trade
issue_id = create_risk_ticket(
    decision_id=decision.id,
    symbol="BTC/USD",
    risk_reason="Position size exceeds limit",
    details={"requested": 1.5, "max_allowed": 1.0}
)
```

---

## n8n Workflow Integration

### Manual Step Required: Create GOV_PLANE_API Credential

The governance workflows reference a credential called `GOV_PLANE_API` that needs to be created in n8n:

1. Open n8n: http://192.168.1.197:5678
2. Go to **Credentials** → **New Credential**
3. Select **Header Auth**
4. Configure:
   - **Name:** `GOV_PLANE_API`
   - **Header Name:** `X-Api-Key`
   - **Header Value:** `${PLANE_API_KEY}`
5. Save

Once created, all governance workflows will be able to create/update Plane issues automatically.

### Environment Variables Available in Workflows

All n8n workflows can now use these variables:

```javascript
// In n8n Function nodes or HTTP Request nodes
$env.PLANE_API_BASE        // http://192.168.1.177:8088
$env.PLANE_WORKSPACE_SLUG  // grovex-tech-solutions
$env.PLANE_PROJECT_ID      // a751111c-fa00-4004-b725-d1174e488fe0
$env.PLANE_API_KEY         // ${PLANE_API_KEY}

// Example: Build issue URL
const issueUrl = `${$env.PLANE_API_BASE}/workspaces/${$env.PLANE_WORKSPACE_SLUG}/projects/${$env.PLANE_PROJECT_ID}/issues/${issueId}`;
```

---

## Existing Issues in Plane

Current FFE-related tickets (as of 2026-02-19):

1. **[FFE ✅ EXECUTED] BTC/USD LONG @ 85.0%** (test issue - can delete)
2. **[FFE EXECUTION BLOCKED] platform_execute breaker open**
3. **[INCIDENT] FFE not opening BTC/ETH trades - investigation**

You can view all issues at:
http://192.168.1.177:8088/grovex-tech-solutions/projects/a751111c-fa00-4004-b725-d1174e488fe0/issues/

---

## API Documentation

### PlaneClient Methods

```python
from ffe_plane_client import PlaneClient

client = PlaneClient()  # Uses env vars automatically

# Create issue
issue = client.create_issue(
    name="Issue title",
    description="Markdown description",
    priority="high"  # urgent, high, medium, low, none
)

# Update issue
client.update_issue(issue_id, name="New title", priority="medium")

# Get issue
issue = client.get_issue(issue_id)

# List issues
issues = client.list_issues(limit=50)

# Add comment
client.add_comment(issue_id, "Comment text")

# FFE-specific helpers
client.create_execution_issue(decision_id, symbol, direction, confidence, error)
client.create_risk_issue(decision_id, symbol, risk_reason, details)
```

### Convenience Functions

```python
from ffe_plane_client import create_execution_ticket, create_risk_ticket

# Returns issue ID or None
issue_id = create_execution_ticket(
    decision_id="uuid",
    symbol="BTC/USD",
    direction="LONG",
    confidence=0.85,
    error=None  # or error message
)

issue_id = create_risk_ticket(
    decision_id="uuid",
    symbol="BTC/USD",
    risk_reason="Exceeded limit",
    details={"key": "value"}
)
```

---

## Integration Points

### Recommended: Log Every Trade Decision

In `core.py` after `execute_decision()`:

```python
from ffe_plane_client import create_execution_ticket

try:
    result = self._execute_trade(decision)
    # Log successful execution
    create_execution_ticket(
        decision_id=decision.id,
        symbol=decision.symbol,
        direction=decision.direction,
        confidence=decision.confidence,
        error=None
    )
except Exception as e:
    # Log failed execution
    create_execution_ticket(
        decision_id=decision.id,
        symbol=decision.symbol,
        direction=decision.direction,
        confidence=decision.confidence,
        error=str(e)
    )
    raise
```

### Recommended: Log Risk Blocks

In risk gatekeeper when blocking trades:

```python
from ffe_plane_client import create_risk_ticket

if position_size > max_position_size:
    create_risk_ticket(
        decision_id=decision.id,
        symbol=decision.symbol,
        risk_reason="Position size exceeds max_position_size",
        details={
            "requested_size": position_size,
            "max_allowed": max_position_size,
            "current_exposure": current_exposure
        }
    )
    raise RiskValidationError("Position size limit exceeded")
```

---

## Testing

```bash
# Test basic connectivity
cd ~/finance_feedback_engine
export PLANE_API_KEY='${PLANE_API_KEY}'
python3 -c "from ffe_plane_client import PlaneClient; c = PlaneClient(); print('✅ Connected to Plane')"

# List FFE issues
python3 examples/plane_ticketing_example.py

# Create test issue
python3 -c "from ffe_plane_client import create_execution_ticket; print(create_execution_ticket('test-123', 'BTC/USD', 'LONG', 0.75))"
```

---

## Troubleshooting

### "PLANE_API_KEY not found"
```bash
export PLANE_API_KEY='${PLANE_API_KEY}'
```

Or add to `~/.zshrc`:
```bash
echo "export PLANE_API_KEY='${PLANE_API_KEY}'" >> ~/.zshrc
source ~/.zshrc
```

### "Connection refused" to 192.168.1.177:8088
- Check Plane container is running: `docker ps | grep plane`
- Check network connectivity: `ping 192.168.1.177`
- Verify Plane is accessible: `curl http://192.168.1.177:8088`

### n8n workflows can't access Plane
- Verify env vars in container: `docker exec n8n env | grep PLANE`
- Verify credential exists: Check n8n UI → Credentials → GOV_PLANE_API
- Check credential has correct header: `X-Api-Key: ${PLANE_API_KEY}`

---

## Next Steps

1. ✅ **Create `GOV_PLANE_API` credential in n8n** (manual step - see above)
2. Test governance workflows that reference Plane
3. Add Plane ticketing calls to FFE core execution paths
4. Review existing Plane issues and triage
5. Set up automatic ticket creation for all FFE trades

---

## Files Changed

- ✅ `/opt/business-tools/.env` (on LXC 200) - Added PLANE_* env vars
- ✅ `/opt/business-tools/docker-compose.yml` (on LXC 200) - Added PLANE_* to n8n service
- ✅ `~/finance_feedback_engine/ffe_plane_client.py` - New integration module
- ✅ `~/finance_feedback_engine/examples/plane_ticketing_example.py` - Usage examples
- ✅ `~/finance_feedback_engine/PLANE_TICKETING_SETUP.md` - This document

**Backups Created:**
- `/opt/business-tools/docker-compose.yml.backup-plane-1771558752`

---

**Status:** Ready to use! Just create the n8n credential and start logging tickets.
