---
name: Phase 2 - Fix Telegram/Redis Integration Tests
about: Update skipped Telegram bot and Redis manager tests with current API
title: "[PHASE-2] Fix Telegram/Redis integration test skips (8 tests)"
labels: ["phase-2", "testing", "telegram", "redis"]
assignees: ""
---

## Overview

8 tests in `tests/test_integrations_telegram_redis.py` are currently skipped due to API changes and outdated test implementations. These need to be updated to match the current `TelegramApprovalBot` and `RedisManager` interfaces.

## Affected Tests

### TelegramApprovalBot Tests (6)

1. **`test_process_update_validates_user`** (Line 62)
   - **Reason**: `process_update` now requires `engine` parameter
   - **Fix**: Add mock engine to test, update call signature

2. **`test_process_update_handles_approval_request`** (Line 82)
   - **Reason**: `process_update` now requires `engine` parameter
   - **Fix**: Add mock engine, update call

3. **`test_create_approval_keyboard`** (Line 96)
   - **Reason**: Keyboard implementation details changed
   - **Fix**: Check actual return type and structure from current implementation

4. **`test_queue_approval_request`** (Line 105)
   - **Reason**: Method renamed to `send_approval_request`
   - **Fix**: Update method call name

5. **`test_format_decision_message`** (Line 121)
   - **Reason**: Needs updated test implementation
   - **Fix**: Verify method exists and works with current signature

6. **`test_handle_callback_query_approve`** (Line 140)
   - **Reason**: `process_update` now requires `engine` parameter
   - **Fix**: Add mock engine, update call

7. **`test_handle_callback_query_reject`** (Line 158)
   - **Reason**: `process_update` now requires `engine` parameter
   - **Fix**: Add mock engine, update call

8. **`test_set_webhook`** (Line 176)
   - **Reason**: Method renamed to `setup_webhook`
   - **Fix**: Update method call name

### RedisManager Tests (Marked as class skip)

- **Reason**: Tests mock subprocess but implementation uses redis library
- **Fix**: Refactor to mock redis library directly

## Current API Reference

### TelegramApprovalBot

```python
async def process_update(self, update_data: Dict[str, Any], engine):
    """Process Telegram webhook update with engine context."""
    
async def send_approval_request(self, decision_id: str, decision: Dict[str, Any]):
    """Send approval request via Telegram."""
    
async def setup_webhook(self, webhook_url: str):
    """Setup Telegram webhook."""
```

## Test Strategy (TDD)

1. **Write failing test** - Update test method with correct API calls
2. **Run test** - Verify it fails with clear error (not skip)
3. **Fix implementation** - Update test setup/mocking as needed
4. **Verify pass** - Ensure test passes

## Acceptance Criteria

- [ ] All 8 skip decorators removed
- [ ] Tests run without skip (pass or fail, not skip)
- [ ] Mock engine fixture added to TelegramApprovalBot test class
- [ ] RedisManager tests refactored to mock redis library
- [ ] All tests pass or converted to appropriate xfail markers
- [ ] Coverage maintained ≥70%

## Files to Modify

- `tests/test_integrations_telegram_redis.py` — Update test methods
- `tests/conftest.py` — Add fixtures if needed

## Related Documentation

- `finance_feedback_engine/integrations/telegram_bot.py` - Current API
- `finance_feedback_engine/integrations/redis_manager.py` - Current API

## Priority

**Medium** — Tests are for external integrations; core functionality works but tests need maintenance.

## Effort Estimate

**4-8 hours** — Depends on refactoring scope for Redis tests.

---

## Implementation Checklist

- [ ] Analyze current `TelegramApprovalBot` and `RedisManager` implementations
- [ ] Update test fixture setup (add mock engine)
- [ ] Fix `process_update` calls (add engine parameter)
- [ ] Rename method calls in tests (`queue_approval_request` → `send_approval_request`, `set_webhook` → `setup_webhook`)
- [ ] Refactor Redis tests to mock redis library
- [ ] Run tests and verify all pass
- [ ] Update any documentation referencing these tests
