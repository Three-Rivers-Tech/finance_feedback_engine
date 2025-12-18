# Quick Start: Quality Assurance

**TL;DR**: Run `./scripts/run_quality_assessment.sh` to assess test health, then follow the plan.

---

## 🚀 For Developers: 3-Minute Quick Start

### 1. Run Assessment (5-10 minutes)
```bash
./scripts/run_quality_assessment.sh
```

### 2. View Results
```bash
# Summary
cat qa_reports/ASSESSMENT_SUMMARY.md

# Coverage (open in browser)
open qa_reports/coverage_run_agent/index.html
open qa_reports/coverage_overall/index.html

# Full test results
less qa_reports/test_results_full.txt
```

### 3. Run Tests Locally
```bash
# All tests
pytest

# Fast tests only (recommended for development)
pytest -m "not slow"

# run-agent tests specifically
pytest -k "run_agent" -v

# With coverage
pytest --cov=finance_feedback_engine --cov-report=html
open htmlcov/index.html
```

### 4. Before Committing
```bash
# Run pre-commit hooks
pre-commit run --all-files

# Or just commit (hooks run automatically)
git commit -m "your message"
```

---

## 📋 For Project Managers: What Was Delivered

### Documents Created
1. **QUALITY_ASSURANCE_PLAN.md** - Comprehensive 5-phase plan (Weeks 1-5)
2. **TODO.md** - 100+ actionable tasks with checkboxes
3. **QA_EXECUTIVE_SUMMARY.md** - High-level overview and status
4. **QUICK_START_QA.md** - This quick reference (you are here)

### Scripts Created
1. **scripts/run_quality_assessment.sh** - Automated assessment tool

### What's Next
- **Week 1**: Run assessment, triage failures, document run-agent paths
- **Week 2**: Fix P0 failures, stabilize tests, pin dependencies
- **Week 3**: Add 35+ new tests for run-agent (unit + integration + smoke)
- **Week 4**: Configure commit gates (pre-commit + CI)
- **Week 5**: Complete documentation (DEVELOPMENT.md, TESTING_GUIDE.md)

---

## 🎯 For Tech Leads: Key Decisions Needed

### Immediate (This Week)
- [ ] **Approve QA Plan**: Review QUALITY_ASSURANCE_PLAN.md
- [ ] **Assign Resources**: Who will execute the assessment?
- [ ] **Set Priorities**: Confirm P0 = blocks run-agent

### Week 2
- [ ] **Coverage Thresholds**: Confirm 70% overall, 85% run-agent
- [ ] **Pre-commit Hooks**: Approve hook configuration
- [ ] **Flaky Test Policy**: How to handle non-deterministic tests?

### Week 4
- [ ] **Branch Protection**: Enable required status checks?
- [ ] **Merge Policy**: Require reviews + passing tests?
- [ ] **Bypass Policy**: When can hooks be bypassed?

---

## 🔧 For DevOps: Infrastructure Tasks

### CI/CD Pipeline
- [ ] Review `.github/workflows/ci-enhanced.yml`
- [ ] Add run-agent specific job (see QUALITY_ASSURANCE_PLAN.md Phase 4.3)
- [ ] Configure branch protection rules
- [ ] Set up Codecov integration

### Monitoring
- [ ] Track test execution times
- [ ] Monitor coverage trends
- [ ] Alert on test failures

### Docker
- [ ] Verify `Dockerfile.ci` builds successfully
- [ ] Ensure CI image has all dependencies

---

## 📊 Success Metrics

### Current (Baseline)
- Tests: 1050+ collected
- Coverage: TBD (run assessment)
- Flaky tests: TBD (run assessment)

### Target (5 Weeks)
- Tests: 1100+ (50+ new)
- Coverage: 75%+ overall, 85%+ run-agent
- Flaky tests: 0
- Test time: <5 min (fast tests)
- CI time: <15 min

---

## 🆘 Common Issues & Solutions

### "Tests fail with import errors"
```bash
pip install -e .
```

### "Tests fail with config errors"
```bash
cp config/config.yaml.example config/config.yaml
```

### "Pre-commit hooks are slow"
```bash
# Only run fast tests
SKIP=run-tests git commit -m "message"
```

### "CI fails but tests pass locally"
```bash
# Use Docker to match CI environment
docker build -f Dockerfile.ci -t ffe-ci .
docker run -it ffe-ci pytest
```

### "How do I debug a specific test?"
```bash
pytest tests/test_agent.py::test_specific -vv --pdb
```

---

## 📚 Full Documentation

- **Comprehensive Plan**: `QUALITY_ASSURANCE_PLAN.md`
- **Task Checklist**: `TODO.md`
- **Executive Summary**: `QA_EXECUTIVE_SUMMARY.md`
- **Existing Testing Gate**: `TESTING_GATE.md`

---

## 🎬 Next Steps

### Right Now
```bash
./scripts/run_quality_assessment.sh
```

### Today
1. Review assessment results
2. Triage test failures (P0, P1, P2, P3)
3. Document findings in `qa_reports/test_analysis.md`

### This Week
1. Complete Phase 1 (Assessment & Triage)
2. Test run-agent from clean environment
3. Identify coverage gaps

### Next 4 Weeks
Follow the 5-phase plan in `QUALITY_ASSURANCE_PLAN.md`

---

## 💡 Pro Tips

1. **Run fast tests frequently**: `pytest -m "not slow"`
2. **Use coverage to find gaps**: `pytest --cov --cov-report=html`
3. **Debug with pdb**: `pytest --pdb` drops into debugger on failure
4. **Run specific tests**: `pytest -k "test_name"` or `pytest tests/test_file.py`
5. **Check flakiness**: `pytest --count=10 -x` runs tests 10 times
6. **Use VS Code Test Explorer**: Install Python extension, configure pytest
7. **Pre-commit hooks save time**: Catch issues before CI

---

## 📞 Questions?

- **About the plan**: See `QUALITY_ASSURANCE_PLAN.md`
- **About specific tasks**: See `TODO.md`
- **About test failures**: Run `./scripts/run_quality_assessment.sh`
- **About run-agent**: See `finance_feedback_engine/cli/commands/agent.py`

---

**Remember**: The goal is to make `run-agent` rock-solid while maintaining developer productivity. Start with the assessment, then follow the incremental plan.

```bash
./scripts/run_quality_assessment.sh && cat qa_reports/ASSESSMENT_SUMMARY.md
