# FFE Stage 55 — Adaptive Control Alert Dispatch Contract Seam

## Why this stage exists

Stage 54 closed the **adaptive control notification delivery contract** seam, formalizing how dashboard-ready state crosses into external notification channels (Telegram, webhooks, alerts) through the delivery contract layer.

The next careful seam in the live repo is the **adaptive control alert dispatch contract**.

This is the layer where validated notification delivery intents are executed into concrete alert dispatches — mapping alert severity, routing rules, and delivery guarantees to actual dispatches. It formalizes the contract between notification delivery intent and alert dispatch execution without collapsing into channel-specific wire protocol details.

## Live repo evidence used for this draft

### Alert dispatch paths already exist
- `finance_feedback_engine/integrations/telegram_bot.py`
  - `send_message(...)` with retry logic
  - `setup_webhook(...)` for incoming callbacks
  - Message formatting and markdown escaping
- `finance_feedback_engine/api/routes.py`
  - `telegram_webhook(...)` handler
  - `handle_alert_webhook(...)` for Alertmanager integration
  - `_validate_webhook_token(...)` / `_validate_webhook_ip(...)`
- `finance_feedback_engine/monitoring/alert_manager.py`
  - `AlertManager` class with alert classification
  - Win-rate and drawdown threshold alerting
  - Alert deduplication and grouping
- `finance_feedback_engine/agent/trading_loop_agent.py`
  - `_validate_notification_config()` for pre-dispatch validation
  - Signal-only mode with alert requirement semantics
- `finance_feedback_engine/api/routes.py`
  - `POST /webhooks/alerts` endpoint
  - Alert payload validation and routing

### Why this stands apart from notification delivery
- Stage 54 captures **delivery intent** — which channels, what content
- Stage 55 captures **dispatch execution** — severity routing, retry guarantees, delivery confirmation
- This preserves the separation between "what should be delivered" and "how delivery is executed"

## Why this is the next honest seam

The live repo separates:
1. Notification delivery intent (Stage 54)
2. Alert dispatch execution (how intents are routed, retried, and confirmed)
3. Channel-specific wire protocol (Telegram Bot API, HTTP webhook POST)

Stage 55 covers the second.

## Stage 55 scope

### Build from
- Stage 54 adaptive-control-notification-delivery-contract summaries
- Alert severity classification and routing
- Dispatch retry guarantees and delivery confirmation
- Alert deduplication and rate limiting

### Still explicitly NOT this stage
- Telegram Bot API wire protocol implementation
- Webhook HTTP client internals
- Alertmanager ingestion protocol
- Thompson posterior/Kelly sizing math

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_adaptive_control_alert_dispatch_contract_set(...)`
2. **PR-2** — `build_policy_selection_adaptive_control_alert_dispatch_contract_summary(...)`
3. **PR-3** — end-to-end adaptive-control-alert-dispatch-contract chain hardening
4. **PR-4** — `extract_policy_selection_adaptive_control_alert_dispatch_contract_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
- derive from live repo evidence, not stale intention alone
- keep one narrow abstraction layer at a time
- prefer policy-facing summaries before channel-specific wire protocol details
- keep the system auditable, understandable, and re-derivable later
