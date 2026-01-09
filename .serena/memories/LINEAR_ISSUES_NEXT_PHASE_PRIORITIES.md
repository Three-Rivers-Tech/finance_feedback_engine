# Linear Issues - Next Phase Priority Assessment
**Date:** January 9, 2026

## ✅ COMPLETED MILESTONES
- **THR-59:** Paper Trading Platform Defaults - DONE
- **THR-61:** E2E First Profitable Trade Test - DONE
- **THR-60:** Risk Gatekeeper Calibration - DONE
- **THR-57:** Autonomous Mode Notification Relaxation - DONE
- **THR-56:** Bot Control API Strict Typing - DONE
- **THR-54:** API Authentication for Bot Control - DONE

**Result:** First profitable trade milestone COMPLETE ✅

---

## 🚀 NEXT PHASE: Scaling to Consistent Profitability

### Phase 3A: Infrastructure Hardening (URGENT - Week 1)

#### **THR-42: TLS/Ingress Hardening** ⚡ URGENT - IN PROGRESS
- **Status:** In Progress (assigned to Christian)
- **Priority:** P0 (Urgent)
- **Impact:** Production deployment security
- **Scope:**
  - cert-manager ClusterIssuer for Let's Encrypt
  - nginx ingress for HTTPS on ffe.three-rivers-tech.com
  - Cloudflare DNS integration
  - TLS secret auto-renewal
- **Blocking:** YES - Required for production deployment
- **Effort:** ~6-8 hours remaining
- **Next Action:** Complete cert-manager setup and verify TLS endpoints

#### **THR-62: Replace Manual Config with Hydra** ⚡ HIGH
- **Status:** Backlog
- **Priority:** P0 (High)
- **Impact:** Config management reliability
- **Problem:**
  - No schema validation (typos silently fail)
  - Precedence logic scattered
  - No composable config groups (dev/prod/backtest)
  - Debugging config precedence opaque
- **Benefits:**
  - Schema validation catches typos at startup
  - Clear precedence rules via Hydra
  - Environment-specific overrides (dev/staging/prod)
  - Better testing with config composition
- **Effort:** 8-12 hours
- **Blocking:** NO - but high ROI for stability
- **Next Action:** Prototype Hydra integration with existing config structure

#### **THR-63: Simplify Model Selection to Debate-Mode Plug-in** ⚡ HIGH
- **Status:** Backlog
- **Priority:** P0 (High)
- **Impact:** User experience & model management
- **Problem:**
  - Model selection flags (--ensemble, local providers) confusing/brittle
  - Users juggle provider flags without clear defaults
- **Solution:**
  - Debate-mode-only model selection layer
  - Curated model list with sensible defaults
  - Single place to configure models
- **Effort:** 6-8 hours
- **Blocking:** NO - but critical UX improvement
- **Next Action:** Design model selection UI/config schema

---

### Phase 3B: Critical Production Gaps (HIGH - Week 1-2)

#### **THR-45: Agent Invalid Config Validation** ⚡ HIGH
- **Status:** Backlog
- **Priority:** P0 (High)
- **Impact:** Agent startup reliability
- **Completion:** Phase 1 (Pydantic validators) COMPLETE ✅
- **Remaining Phases:**
  - Phase 2: Trading platform validation
  - Phase 3: Risk limits validation
  - Phase 4: Data provider connectivity checks
- **Effort:** 4-6 hours (remaining phases)
- **Blocking:** NO - Phase 1 done, rest is polish
- **Next Action:** Implement Phase 2 platform validation

#### **THR-55: WebSocket Authentication** ⚡ HIGH
- **Status:** Backlog
- **Priority:** P0 (High)
- **Impact:** Security alignment with HTTP endpoints
- **Scope:**
  - Accept API key via query param (?token=) or Sec-WebSocket-Protocol
  - Validate using get_auth_manager_instance()
  - Close unauthenticated connections (4001 code)
- **Effort:** 3-4 hours
- **Blocking:** NO - but critical for security
- **Next Action:** Implement WS auth in bot_control WebSocket handlers

#### **THR-58: Asset Pair Validation at Config Load** 🔶 MEDIUM
- **Status:** Backlog
- **Priority:** P1 (Medium)
- **Impact:** Runtime error prevention
- **Scope:**
  - Enforce standardize_asset_pair() for all configured pairs
  - Reject invalid pairs with clear error
  - Update frontend to show normalized format
- **Effort:** 2-3 hours
- **Blocking:** NO - but improves reliability
- **Next Action:** Add validator to agent config init

---

### Phase 3C: Frontend Security & Polish (MEDIUM - Week 2)

#### **THR-46: Frontend API Key Input & 401 Handling** ⚡ HIGH
- **Status:** Backlog
- **Priority:** P0 (High)
- **Impact:** Frontend auth UX
- **Scope:**
  - AgentControl page prompts for API key on 401
  - Store key in localStorage (with optional clear)
  - Show 401 errors proactively
- **Effort:** 4-5 hours
- **Blocking:** NO - backend auth already works
- **Next Action:** Add API key prompt modal to AgentControl

#### **THR-47: WebSocket Auth for Agent Streams** ⚡ HIGH
- **Status:** Backlog
- **Priority:** P0 (High)
- **Impact:** Frontend stream security
- **Scope:**
  - Update useAgentStream to include API key in WS connection
  - Handle 4001 close codes with friendly prompt
  - Exponential backoff reconnect after re-auth
- **Effort:** 3-4 hours
- **Blocking:** NO - depends on THR-55
- **Next Action:** Update useAgentStream hook after THR-55 complete

---

### Phase 3D: Infrastructure Maturity (URGENT - Week 1)

#### **THR-39: Terraform Baseline** ✅ DONE
- **Status:** Complete
- **Scope:** Network, LB, storage, Vault bootstrap
- **Delivered:** Ubuntu on-prem deployment foundation

#### **THR-40: Helm Charts** ✅ DONE
- **Status:** Complete
- **Scope:** Backend deployment, Postgres, nginx ingress, cert-manager
- **Delivered:** Production-ready Helm charts

#### **THR-41: CI/CD Wiring** 🔴 BACKLOG - URGENT
- **Status:** Backlog
- **Priority:** P0 (Urgent)
- **Impact:** Deployment automation
- **Scope:**
  - Terraform plan/apply stages
  - Helm install/upgrade per environment
  - Alembic migrations pre-deployment
  - Health checks post-deployment
  - Backup/restore operations
- **Effort:** 8-12 hours
- **Blocking:** YES - Required for automated deployments
- **Next Action:** Wire Terraform plan/apply into GitHub Actions

#### **THR-43: Vault Secret Management** 🔶 HIGH
- **Status:** Backlog
- **Priority:** P1 (High)
- **Impact:** Secret rotation & mTLS monitoring
- **Scope:**
  - Vault namespace layout (secret/database/pki/transit)
  - Dynamic database credentials (TTL auto-rotation)
  - PKI for TLS certificates
  - mTLS monitoring runbook
- **Effort:** 6-8 hours
- **Blocking:** NO - but critical for production ops
- **Next Action:** Implement Vault namespace layout

#### **THR-44: Docs Refresh (Postgres, Terraform/Helm)** 🔶 HIGH
- **Status:** Backlog
- **Priority:** P1 (High)
- **Impact:** Documentation accuracy
- **Scope:**
  - Remove SQLite references
  - Document Terraform/Helm/Vault flow
  - Update deployment readiness docs
- **Effort:** 4-6 hours
- **Blocking:** NO - but critical for team alignment
- **Next Action:** Audit and update deployment docs

---

### Phase 4: Reliability & Observability (MEDIUM - Week 2-3)

#### **THR-37: Unclosed Async Sessions** ⚡ HIGH
- **Status:** Backlog
- **Priority:** P0 (High)
- **Impact:** Resource leaks in production
- **Root Cause:**
  - AlphaVantageProvider not closing async sessions properly
  - aiohttp ClientSession leaks
- **Effort:** 2-3 hours
- **Blocking:** NO - but impacts long-running stability
- **Next Action:** Audit all async session lifecycle

#### **THR-36: Missing Parquet Dependencies** 🔶 MEDIUM
- **Status:** Backlog
- **Priority:** P1 (Medium)
- **Impact:** Timeseries data persistence
- **Problem:** pyarrow/fastparquet not installed
- **Solution:** Add pyarrow to requirements.txt
- **Effort:** 15 minutes
- **Blocking:** NO
- **Next Action:** Add pyarrow==15.0.0 to requirements

#### **THR-35: Pulse Formatter Coroutine Error** ⚡ HIGH
- **Status:** Backlog
- **Priority:** P0 (High)
- **Impact:** CLI pulse display
- **Root Cause:** fetch_pulse() coroutine not awaited
- **Effort:** 30 minutes
- **Blocking:** NO - CLI only
- **Next Action:** Wrap fetch_pulse() with asyncio.run()

#### **THR-34: Trade Tracker Mock Iteration Error** ⚡ HIGH
- **Status:** Backlog
- **Priority:** P0 (High)
- **Impact:** Test reliability
- **Root Cause:** Mock positions object not iterable
- **Effort:** 30 minutes
- **Blocking:** NO - test issue only
- **Next Action:** Fix mock return value in test fixtures

---

### Phase 5: Lower Priority Improvements (LOW - Deferred)

#### **THR-50: Stream Resilience & Polling Fallback** 🔶 MEDIUM
- **Status:** Backlog
- **Priority:** P1 (Medium)
- **Impact:** Frontend resilience
- **Scope:** Exponential backoff, WS→HTTP fallback
- **Effort:** 4-5 hours
- **Blocking:** NO

#### **THR-51: Type-Safe DTOs** 🔶 MEDIUM
- **Status:** Backlog
- **Priority:** P1 (Medium)
- **Impact:** Frontend type safety
- **Effort:** 3-4 hours
- **Blocking:** NO

#### **THR-52: Axios Interceptor Tests** 🔶 MEDIUM
- **Status:** Backlog
- **Priority:** P1 (Medium)
- **Impact:** Frontend test coverage
- **Effort:** 2-3 hours
- **Blocking:** NO

#### **THR-53: API Key Docs in UI** 🔵 LOW
- **Status:** Backlog
- **Priority:** P2 (Low)
- **Impact:** User documentation
- **Effort:** 1-2 hours
- **Blocking:** NO

---

## 🎯 RECOMMENDED SPRINT PLAN

### Sprint 1: Production Security & Infrastructure (Week 1)
**Goal:** Make production deployment secure and automated

1. **THR-42:** TLS/Ingress Hardening (COMPLETE IN PROGRESS)
2. **THR-41:** CI/CD Wiring (Terraform/Helm automation)
3. **THR-55:** WebSocket Authentication
4. **THR-62:** Hydra Config Migration (start)

**Total Effort:** 20-26 hours
**Priority:** All P0/Urgent
**Gating:** Production deployment readiness

---

### Sprint 2: Config & Model Management (Week 2)
**Goal:** Simplify config management and model selection UX

1. **THR-62:** Hydra Config Migration (complete)
2. **THR-63:** Model Selection Debate-Mode Plug-in
3. **THR-45:** Agent Config Validation (remaining phases)
4. **THR-46:** Frontend API Key Input
5. **THR-47:** Frontend WebSocket Auth

**Total Effort:** 24-30 hours
**Priority:** High (UX & reliability)
**Gating:** User experience improvements

---

### Sprint 3: Stability & Observability (Week 3)
**Goal:** Fix resource leaks and improve monitoring

1. **THR-37:** Unclosed Async Sessions
2. **THR-43:** Vault Secret Management
3. **THR-44:** Docs Refresh
4. **THR-58:** Asset Pair Validation
5. **THR-35:** Pulse Formatter Fix
6. **THR-34:** Trade Tracker Mock Fix
7. **THR-36:** Add Parquet Dependencies

**Total Effort:** 16-22 hours
**Priority:** Medium (production ops)
**Gating:** Long-term reliability

---

## 📊 CRITICAL METRICS

### First Profitable Trade Milestone: ✅ COMPLETE
- Paper trading operational
- Profitable trade executed: +$200 (+2% ROI)
- 5/5 integration tests passing
- Autonomous OODA loop verified

### Next Milestone: Sustained Profitability
- **Target:** 5 consecutive profitable trades in paper trading
- **Blockers:**
  - Production infrastructure (THR-42, THR-41)
  - Config reliability (THR-62)
  - Model selection UX (THR-63)
- **Timeline:** 3 weeks (sprints 1-3)

---

## 🚫 DEFERRED ISSUES (Phase 4+)

These are important but not blocking sustained profitability:

- THR-48: Agent Control Error Feedback
- THR-49: API Base URL Normalization
- THR-50: Stream Resilience
- THR-51: Type-Safe DTOs
- THR-52: Axios Interceptor Tests
- THR-53: API Key Documentation
- THR-13: Phase 1 Test Coverage (20.8% complete)
- THR-20: Performance Optimization
- THR-19: Test Coverage 70%

---

**Last Updated:** 2026-01-09
**Next Review:** After Sprint 1 completion (THR-42, THR-41, THR-55)
