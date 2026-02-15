# FFE Sub-Agent Hierarchy Design

**Date:** 2026-02-14  
**Purpose:** Specialized agent delegation for complex software engineering tasks  
**Inspiration:** Agyn (72.2% SWE-bench), MetaGPT, industry multi-agent patterns  
**Philosophy:** Code = SOP(Team) — Materialize team structure and apply to LLM agents

---

## Core Principle: Specialization Over General Intelligence

**Problem:** General-purpose agents burn tokens on tasks outside their expertise  
**Solution:** Specialized agents with clear roles, responsibilities, and skill sets  
**Benefit:** Lower token usage, higher quality, parallel execution

---

## Agent Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│         PROJECT MANAGER (Orchestrator)                  │
│  • Task decomposition                                   │
│  • Agent delegation                                     │
│  • Progress tracking                                    │
│  • Final integration review                             │
│  • Model: Opus (complex reasoning)                      │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┴──────────┬────────────┬──────────────┬──────────────┐
        │                     │            │              │              │
   ┌────▼────┐          ┌────▼────┐  ┌────▼────┐    ┌────▼────┐   ┌────▼────┐
   │ RESEARCH│          │SOFTWARE │  │   QA    │    │ DEVOPS  │   │SECURITY │
   │  AGENT  │          │   DEV   │  │  LEAD   │    │ ENGINEER│   │ REVIEWER│
   └─────────┘          └────┬────┘  └─────────┘    └─────────┘   └─────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
               ┌────▼────┐      ┌────▼────┐
               │BACKEND  │      │FRONTEND │
               │   DEV   │      │   DEV   │
               └─────────┘      └─────────┘
                    │                 │
                    │    ┌────────────┘
                    │    │
               ┌────▼────▼────┐
               │CODE REVIEWER │
               │(Gemini Cross)│
               └──────────────┘
```

---

## Agent Roles & Specifications

### 1. PROJECT MANAGER (PM)
**Model:** Claude Opus 4 (complex reasoning)  
**Responsibility:** Task orchestration and final integration  
**Token budget:** 100K-200K (long context needed)

**Core skills:**
- Task decomposition (break complex features into atomic tasks)
- Agent capability matching (assign right agent to right task)
- Dependency management (ensure correct execution order)
- Progress monitoring (track sub-agent status)
- Integration review (validate all pieces fit together)
- Conflict resolution (handle agent disagreements)

**Inputs:**
- High-level task from Christian or main agent
- Project context and constraints
- Available agent pool

**Outputs:**
- Task breakdown document
- Agent assignments with clear specifications
- Integration report
- Final deliverable validation

**When to use:**
- Complex multi-part features (e.g., SHORT backtesting)
- Cross-cutting concerns (e.g., security + performance)
- Large refactors requiring coordination

**Skill configuration:**
```yaml
role: project_manager
model: claude-opus-4
context_window: 200000
specialization:
  - task_decomposition
  - software_architecture
  - team_coordination
  - risk_assessment
  - integration_testing
tools_available:
  - sessions_spawn
  - sessions_list
  - sessions_send
  - git
  - linear
constraints:
  - Must create detailed task specs for sub-agents
  - Must validate deliverables meet requirements
  - Must track token usage across team
```

---

### 2. RESEARCH AGENT
**Model:** Claude Sonnet 4 (balanced)  
**Responsibility:** Investigation, analysis, and design research  
**Token budget:** 50K-100K

**Core skills:**
- Literature review (arXiv, GitHub, industry sources)
- Competitive analysis (similar systems/frameworks)
- Design pattern research (best practices)
- Technology evaluation (libraries, tools, approaches)
- Prototyping exploration (proof of concepts)

**Inputs:**
- Research question or design problem
- Domain context
- Success criteria

**Outputs:**
- Research report with findings
- Design recommendations
- Comparative analysis
- Implementation guidance

**When to use:**
- New feature design (e.g., agent memory architecture)
- Technology selection (which backtesting library?)
- Performance optimization research
- Security pattern investigation

**Skill configuration:**
```yaml
role: research_agent
model: claude-sonnet-4
context_window: 100000
specialization:
  - academic_research
  - competitive_analysis
  - design_patterns
  - technology_evaluation
  - documentation_synthesis
tools_available:
  - web_search
  - web_fetch
  - read (documentation)
output_format: markdown_report
```

---

### 3. SOFTWARE DEVELOPER (Backend)
**Model:** Claude Sonnet 4 (cost-effective for coding)  
**Responsibility:** Backend implementation (Python, APIs, algorithms)  
**Token budget:** 50K-100K

**Core skills:**
- Python development (FFE codebase fluency)
- Algorithmic implementation
- API design and integration
- Data structures and optimization
- Async/concurrent programming
- Database operations (SQLAlchemy, Postgres)

**Inputs:**
- Technical specification from PM
- Code context (relevant files)
- Test requirements

**Outputs:**
- Implementation code
- Unit tests
- Documentation comments
- Integration notes

**When to use:**
- Backend logic (decision engine, risk management)
- Data processing (backtesting, P&L calculations)
- API endpoints
- Database schema changes

**Skill configuration:**
```yaml
role: backend_developer
model: claude-sonnet-4
context_window: 100000
specialization:
  - python
  - fastapi
  - asyncio
  - sqlalchemy
  - pandas
  - numpy
  - pytest
coding_standards:
  - file: ~/finance_feedback_engine/.editorconfig
  - linter: ruff
  - formatter: black
  - type_checker: mypy
tools_available:
  - read
  - write
  - edit
  - exec (pytest, linter)
test_requirements: 70%_coverage_minimum
```

---

### 4. SOFTWARE DEVELOPER (Frontend)
**Model:** Claude Sonnet 4  
**Responsibility:** Frontend implementation (React, TypeScript, UI/UX)  
**Token budget:** 50K-100K

**Core skills:**
- React development
- TypeScript
- Component design
- State management (Redux/Context)
- API integration
- Responsive design
- Accessibility (WCAG)

**Inputs:**
- UI/UX requirements
- Design mockups or wireframes
- Backend API specifications

**Outputs:**
- React components
- TypeScript interfaces
- CSS/styling
- Integration tests (React Testing Library)

**When to use:**
- Dashboard visualizations
- Trading UI components
- Configuration interfaces
- Reporting views

**Skill configuration:**
```yaml
role: frontend_developer
model: claude-sonnet-4
context_window: 100000
specialization:
  - react
  - typescript
  - css
  - html
  - javascript
  - react_testing_library
coding_standards:
  - linter: eslint
  - formatter: prettier
  - type_checker: typescript
tools_available:
  - read
  - write
  - edit
  - exec (npm test, build)
accessibility: wcag_2.1_aa_required
```

---

### 5. QA LEAD (Testing & Quality)
**Model:** Claude Sonnet 4  
**Responsibility:** Test strategy, test implementation, quality assurance  
**Token budget:** 50K-100K

**Core skills:**
- Test strategy design (unit, integration, E2E)
- Pytest mastery
- Mock/fixture design
- Coverage analysis
- Edge case identification
- Regression testing
- Performance testing

**Inputs:**
- Feature specification
- Implementation code
- Test coverage requirements

**Outputs:**
- Test plan
- Test implementation
- Coverage report
- Bug reports

**When to use:**
- New feature testing
- Regression test suites
- Critical path validation
- Test coverage improvement (RALPH-like tasks)

**Skill configuration:**
```yaml
role: qa_lead
model: claude-sonnet-4
context_window: 100000
specialization:
  - pytest
  - unittest_mock
  - hypothesis_testing
  - coverage_analysis
  - regression_testing
  - performance_profiling
tools_available:
  - read
  - write
  - exec (pytest, coverage)
test_frameworks:
  - pytest
  - pytest-asyncio
  - pytest-cov
  - pytest-mock
coverage_target: 70%_minimum
```

---

### 6. CODE REVIEWER (Cross-Model Validation)
**Model:** Gemini 3 Pro (different perspective)  
**Responsibility:** Code review, quality validation, design critique  
**Token budget:** 30K-50K

**Core skills:**
- Code quality assessment
- Security vulnerability detection
- Performance bottleneck identification
- Design pattern validation
- Best practice enforcement
- Constructive feedback

**Inputs:**
- Implementation code
- Context (what problem it solves)
- Standards/requirements

**Outputs:**
- Code review report
- Rating (1-10 scale)
- Prioritized issues (Critical/High/Medium/Low)
- Specific fix recommendations

**When to use:**
- Post-implementation review (before merge)
- Critical code paths (trading execution, risk)
- Major refactors
- Performance-sensitive code

**Skill configuration:**
```yaml
role: code_reviewer
model: gemini-3-pro
context_window: 50000
specialization:
  - code_review
  - security_analysis
  - performance_analysis
  - design_patterns
  - python_best_practices
review_criteria:
  - correctness
  - security
  - performance
  - maintainability
  - testability
  - documentation
output_format: structured_review_with_rating
```

---

### 7. DEVOPS ENGINEER
**Model:** Claude Sonnet 4  
**Responsibility:** Infrastructure, deployment, monitoring, CI/CD  
**Token budget:** 30K-50K

**Core skills:**
- Docker/docker-compose
- CI/CD pipelines (GitHub Actions)
- Infrastructure as Code (Terraform, if needed)
- Monitoring setup (Prometheus, Grafana)
- Log analysis
- Performance tuning
- Database administration

**Inputs:**
- Deployment requirements
- Infrastructure changes needed
- Performance/monitoring goals

**Outputs:**
- Docker configurations
- CI/CD pipeline updates
- Monitoring dashboards
- Deployment scripts

**When to use:**
- Production deployment
- Infrastructure changes
- Performance optimization
- Monitoring/alerting setup
- Database migrations

**Skill configuration:**
```yaml
role: devops_engineer
model: claude-sonnet-4
context_window: 50000
specialization:
  - docker
  - docker_compose
  - github_actions
  - prometheus
  - grafana
  - postgres_admin
  - nginx
  - systemd
tools_available:
  - read
  - write
  - exec (docker, docker-compose)
infrastructure_focus: ffe_production_stack
```

---

### 8. SECURITY REVIEWER
**Model:** Claude Sonnet 4  
**Responsibility:** Security audits, vulnerability detection, threat modeling  
**Token budget:** 30K-50K

**Core skills:**
- Security vulnerability scanning
- OWASP Top 10 knowledge
- Secrets detection
- Input validation review
- Authentication/authorization review
- API security
- Threat modeling

**Inputs:**
- Code to audit
- API endpoints
- Data flow diagrams

**Outputs:**
- Security audit report
- Vulnerability list (CVSS scored)
- Remediation recommendations
- Threat model

**When to use:**
- Pre-production security review
- API endpoint changes
- Authentication changes
- External integrations
- Sensitive data handling

**Skill configuration:**
```yaml
role: security_reviewer
model: claude-sonnet-4
context_window: 50000
specialization:
  - owasp_top_10
  - secrets_detection
  - input_validation
  - authentication_security
  - api_security
  - threat_modeling
scan_tools:
  - bandit (Python)
  - semgrep
  - gitleaks
output_format: cvss_scored_vulnerabilities
```

---

## Communication Protocol

### Task Delegation Flow

1. **PM receives high-level task** from Christian or main agent
2. **PM decomposes task** into atomic sub-tasks
3. **PM creates spec for each sub-task:**
   - Clear objective
   - Input context
   - Success criteria
   - Constraints
4. **PM spawns sub-agents** with specifications
5. **Sub-agents work independently** in parallel (where possible)
6. **Sub-agents deliver outputs** to PM
7. **PM integrates and validates** deliverables
8. **PM triggers Code Reviewer** for final validation
9. **PM reports completion** to main agent/Christian

### Inter-Agent Communication

**Direct delegation (PM → Agent):**
```yaml
task_spec:
  objective: "Implement SHORT position backtesting"
  role: backend_developer
  inputs:
    - backtester.py (current implementation)
    - Backtesting.py framework pattern (research)
  outputs:
    - Modified backtester.py
    - Unit tests (test_short_backtesting.py)
    - Coverage report
  success_criteria:
    - 10+ SHORT trades in backtest
    - Correct P&L calculation
    - 70%+ test coverage
  constraints:
    - No breaking changes to existing LONG logic
    - Must follow existing code style
```

**Peer review (Developer → Reviewer):**
```yaml
review_request:
  code_location: backtester.py
  changes_made:
    - Added SHORT entry on SELL signal
    - Inverted SL/TP triggers
    - Updated P&L calculation
  context: "SHORT position support for futures trading"
  review_focus:
    - Correctness of inverted logic
    - Edge cases
    - Performance impact
```

---

## Token Optimization Strategy

### Model Selection by Task Complexity

| Complexity | Model | Use Case | Cost/1M Tokens |
|------------|-------|----------|----------------|
| Simple | Haiku | Quick tasks, repetitive | $0.25 |
| Moderate | Sonnet 4 | Most dev work | $3.00 |
| Complex | Opus 4 | Architecture, PM | $15.00 |
| Cross-validate | Gemini 3 Pro | Code review | $2.50 |

### Token Budget Allocation (Example: SHORT Backtesting)

| Agent | Budget | Actual (Est) | Savings vs General |
|-------|--------|--------------|-------------------|
| PM | 50K | 30K | -30% (focused orchestration) |
| Research | 50K | 40K | -20% (targeted search) |
| Backend Dev | 100K | 80K | -40% (no research overhead) |
| QA Lead | 50K | 40K | -30% (testing focus only) |
| Code Reviewer | 30K | 20K | -50% (concise feedback) |
| **Total** | **280K** | **210K** | **-25% overall** |

**Savings:** Specialization reduces token waste by ~25-40% per agent

---

## Implementation: SHORT Backtesting Task

### Task Breakdown (PM View)

**Phase 1: Research** (Research Agent)
- [ ] Analyze Backtesting.py SHORT handling
- [ ] Review FFE current backtester.py
- [ ] Design SHORT logic integration
- Output: RESEARCH_SHORT_BACKTESTING.md

**Phase 2: Implementation** (Backend Dev)
- [ ] Modify backtester.py (SELL = short entry)
- [ ] Implement inverted SL/TP
- [ ] Update P&L calculation
- Output: Code changes

**Phase 3: Testing** (QA Lead)
- [ ] Write unit tests for SHORT logic
- [ ] Run backtest on falling market data
- [ ] Measure coverage
- Output: Test suite + coverage report

**Phase 4: Review** (Code Reviewer - Gemini)
- [ ] Review SHORT implementation
- [ ] Check edge cases
- [ ] Validate performance
- Output: Review report (rating + issues)

**Phase 5: Integration** (PM)
- [ ] Validate all outputs
- [ ] Run regression tests
- [ ] Create summary report
- Output: SHORT_BACKTESTING_COMPLETE.md

---

## Agent Pool Management

### Available Agents (by Label)

```yaml
research:
  label: "research"
  model: claude-sonnet-4
  specialization: [research, design, analysis]

backend_dev:
  label: "backend-dev"
  model: claude-sonnet-4
  specialization: [python, fastapi, algorithms]

frontend_dev:
  label: "frontend-dev"
  model: claude-sonnet-4
  specialization: [react, typescript, ui]

qa_lead:
  label: "qa-lead"
  model: claude-sonnet-4
  specialization: [testing, quality, coverage]

code_reviewer_gemini:
  label: "code-reviewer"
  model: gemini-3-pro
  specialization: [review, validation, critique]

devops:
  label: "devops"
  model: claude-sonnet-4
  specialization: [docker, deployment, monitoring]

security:
  label: "security"
  model: claude-sonnet-4
  specialization: [security, vulnerabilities, owasp]

project_manager:
  label: "pm"
  model: claude-opus-4
  specialization: [orchestration, architecture, integration]
```

---

## Success Metrics

### Agent Performance

Track per agent:
- **Token efficiency:** Actual vs budget
- **Quality:** Code review ratings, test pass rate
- **Speed:** Time to completion
- **Collaboration:** Handoff smoothness

### Team Performance

Track overall:
- **Cost reduction:** vs general-purpose approach
- **Parallelization:** Tasks run simultaneously
- **Quality:** Fewer bugs, higher coverage
- **Velocity:** Features delivered per week

---

## Next Steps

1. **Implement PM agent** (first priority)
   - Create PM system prompt with SOP
   - Test on SHORT backtesting task
   - Measure token savings

2. **Build agent library** (second priority)
   - Formalize each agent's system prompt
   - Create standard task spec format
   - Build communication protocol

3. **Deploy to production** (third priority)
   - Use for all complex features
   - Track metrics
   - Iterate on agent designs

---

**Philosophy:** "Code = SOP(Team)" — The best software comes from well-organized teams with clear roles and communication. Let's materialize that with LLM agents.
