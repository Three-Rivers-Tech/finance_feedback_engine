#!/bin/bash
# Quality Assessment Script for Finance Feedback Engine 2.0
# This script runs the initial assessment phase of the QA plan

set -e

echo "🔍 Finance Feedback Engine 2.0 - Quality Assessment"
echo "=================================================="
echo ""

# Create output directory
OUTPUT_DIR="qa_reports"
mkdir -p "$OUTPUT_DIR"

echo "📊 Step 1: Running full test suite..."
echo "This may take several minutes..."
pytest -v --tb=short --maxfail=0 > "$OUTPUT_DIR/test_results_full.txt" 2>&1 || true
pytest --junit-xml="$OUTPUT_DIR/test-results.xml" --html="$OUTPUT_DIR/test-report.html" --self-contained-html -q 2>&1 || true
echo "✅ Test results saved to $OUTPUT_DIR/test_results_full.txt"
echo ""

echo "📈 Step 2: Generating test statistics..."
echo "Total tests collected:"
pytest --collect-only -q 2>&1 | tail -1
echo ""

echo "Test results summary:"
grep -E "passed|failed|error|skipped" "$OUTPUT_DIR/test_results_full.txt" | tail -5 || echo "Could not extract summary"
echo ""

echo "📊 Step 3: Generating coverage report for run-agent..."
pytest --cov=finance_feedback_engine.cli.commands.agent \
       --cov=finance_feedback_engine.agent \
       --cov-report=html:"$OUTPUT_DIR/coverage_run_agent" \
       --cov-report=term-missing \
       tests/test_agent.py tests/test_trading_loop_agent.py tests/cli/ \
       > "$OUTPUT_DIR/coverage_run_agent.txt" 2>&1 || true
echo "✅ Coverage report saved to $OUTPUT_DIR/coverage_run_agent/"
echo ""

echo "📊 Step 4: Generating overall coverage report..."
pytest --cov=finance_feedback_engine \
       --cov-report=html:"$OUTPUT_DIR/coverage_overall" \
       --cov-report=term-missing \
       -m "not slow" \
       > "$OUTPUT_DIR/coverage_overall.txt" 2>&1 || true
echo "✅ Overall coverage report saved to $OUTPUT_DIR/coverage_overall/"
echo ""

echo "🔍 Step 5: Analyzing test failures..."
echo "Categorizing failures by type..."

# Extract failures
grep -A 5 "FAILED" "$OUTPUT_DIR/test_results_full.txt" > "$OUTPUT_DIR/failures.txt" 2>/dev/null || echo "No failures found or could not extract"

# Count failure types
echo "Failure analysis:" > "$OUTPUT_DIR/failure_analysis.txt"
echo "==================" >> "$OUTPUT_DIR/failure_analysis.txt"
echo "" >> "$OUTPUT_DIR/failure_analysis.txt"

echo "Import errors:" >> "$OUTPUT_DIR/failure_analysis.txt"
grep -i "importerror\|modulenotfounderror" "$OUTPUT_DIR/test_results_full.txt" | wc -l >> "$OUTPUT_DIR/failure_analysis.txt" 2>/dev/null || echo "0" >> "$OUTPUT_DIR/failure_analysis.txt"

echo "" >> "$OUTPUT_DIR/failure_analysis.txt"
echo "Assertion errors:" >> "$OUTPUT_DIR/failure_analysis.txt"
grep -i "assertionerror" "$OUTPUT_DIR/test_results_full.txt" | wc -l >> "$OUTPUT_DIR/failure_analysis.txt" 2>/dev/null || echo "0" >> "$OUTPUT_DIR/failure_analysis.txt"

echo "" >> "$OUTPUT_DIR/failure_analysis.txt"
echo "Timeout errors:" >> "$OUTPUT_DIR/failure_analysis.txt"
grep -i "timeout" "$OUTPUT_DIR/test_results_full.txt" | wc -l >> "$OUTPUT_DIR/failure_analysis.txt" 2>/dev/null || echo "0" >> "$OUTPUT_DIR/failure_analysis.txt"

echo "" >> "$OUTPUT_DIR/failure_analysis.txt"
echo "Configuration errors:" >> "$OUTPUT_DIR/failure_analysis.txt"
grep -i "configerror\|config.*not found" "$OUTPUT_DIR/test_results_full.txt" | wc -l >> "$OUTPUT_DIR/failure_analysis.txt" 2>/dev/null || echo "0" >> "$OUTPUT_DIR/failure_analysis.txt"

cat "$OUTPUT_DIR/failure_analysis.txt"
echo ""

echo "🧪 Step 6: Testing run-agent from clean environment..."
echo "Creating temporary virtual environment..."
TEMP_DIR=$(mktemp -d)
TEMP_VENV="$TEMP_DIR/test_venv"
trap 'rm -rf "$TEMP_DIR"' EXIT
python -m venv "$TEMP_VENV"
source "$TEMP_VENV/bin/activate"

echo "Installing package..."
pip install -q --upgrade pip
pip install -q -e . > "$OUTPUT_DIR/clean_install.log" 2>&1 || true

echo "Testing run-agent --help via installed entry..."
# Prefer installed console script; fallback to module invocation
if command -v ffe >/dev/null 2>&1; then
    ffe run-agent --help > "$OUTPUT_DIR/run_agent_help.txt" 2>&1 && echo "✅ run-agent --help works" || echo "❌ run-agent --help failed"
else
    python -m finance_feedback_engine.cli.main run-agent --help > "$OUTPUT_DIR/run_agent_help.txt" 2>&1 && echo "✅ run-agent --help works" || echo "❌ run-agent --help failed"
fi

deactivate
rm -rf "$TEMP_DIR"
echo ""

echo "📋 Step 7: Checking for flaky tests..."
echo "Running fast tests 3 times to detect flakes..."
for i in 1 2 3; do
    echo "Run $i/3..."
    pytest -m "not slow" --tb=line -q > "$OUTPUT_DIR/flaky_test_run_$i.txt" 2>&1 || true
done

echo "Comparing results..."
diff "$OUTPUT_DIR/flaky_test_run_1.txt" "$OUTPUT_DIR/flaky_test_run_2.txt" > "$OUTPUT_DIR/flaky_diff_1_2.txt" 2>&1 || echo "Differences found between run 1 and 2"
diff "$OUTPUT_DIR/flaky_test_run_2.txt" "$OUTPUT_DIR/flaky_test_run_3.txt" > "$OUTPUT_DIR/flaky_diff_2_3.txt" 2>&1 || echo "Differences found between run 2 and 3"
echo ""

echo "📊 Step 8: Generating summary report..."
cat > "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md" << 'EOF'
# Quality Assessment Summary

## Test Execution Results

### Overall Statistics
EOF

echo "\`\`\`" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
pytest --collect-only -q 2>&1 | tail -1 >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
grep -E "passed|failed|error|skipped" "$OUTPUT_DIR/test_results_full.txt" | tail -5 >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md" 2>/dev/null || echo "Could not extract summary" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
echo "\`\`\`" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"

cat >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md" << 'EOF'

### Failure Analysis

EOF

cat "$OUTPUT_DIR/failure_analysis.txt" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"

cat >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md" << 'EOF'

## Coverage Analysis

### run-agent Coverage
See detailed report: `qa_reports/coverage_run_agent/index.html`

### Overall Coverage
See detailed report: `qa_reports/coverage_overall/index.html`

## run-agent Testing

### Clean Environment Test
EOF

if grep -q "✅" "$OUTPUT_DIR/run_agent_help.txt" 2>/dev/null; then
    echo "✅ run-agent --help works from clean environment" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
else
    echo "❌ run-agent --help failed from clean environment" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
    echo "" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
    echo "Error details:" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
    echo "\`\`\`" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
    tail -20 "$OUTPUT_DIR/clean_install.log" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md" 2>/dev/null || echo "No error log available" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
    echo "\`\`\`" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
fi

cat >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md" << 'EOF'

## Flaky Tests

EOF

if [ -s "$OUTPUT_DIR/flaky_diff_1_2.txt" ] || [ -s "$OUTPUT_DIR/flaky_diff_2_3.txt" ]; then
    echo "⚠️ Potential flaky tests detected. See:" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
    echo "- \`qa_reports/flaky_diff_1_2.txt\`" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
    echo "- \`qa_reports/flaky_diff_2_3.txt\`" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
else
    echo "✅ No obvious flaky tests detected in 3 runs" >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
fi

cat >> "$OUTPUT_DIR/ASSESSMENT_SUMMARY.md" << 'EOF'

## Next Steps

Based on this assessment:

1. **Review Failures**: Check `qa_reports/test_results_full.txt` for detailed failure information
2. **Prioritize Fixes**: Focus on P0 failures that block run-agent functionality
3. **Improve Coverage**: Target areas with low coverage, especially run-agent (goal: 85%+)
4. **Fix Flaky Tests**: Address any non-deterministic test behavior
5. **Update Documentation**: Document any setup requirements discovered

## Files Generated

- `test_results_full.txt` - Complete test output
- `test-results.xml` - JUnit XML format for CI integration
- `test-report.html` - HTML test report
- `coverage_run_agent/` - Coverage report for run-agent
- `coverage_overall/` - Overall coverage report
- `failures.txt` - Extracted failure details
- `failure_analysis.txt` - Categorized failure counts
- `run_agent_help.txt` - run-agent help output test
- `clean_install.log` - Clean environment installation log
- `flaky_test_run_*.txt` - Multiple test runs for flake detection
- `ASSESSMENT_SUMMARY.md` - This summary report

## Viewing Reports

### Coverage Reports (HTML)
```bash
# run-agent coverage
open qa_reports/coverage_run_agent/index.html

# Overall coverage
open qa_reports/coverage_overall/index.html

# Test report
open qa_reports/test-report.html
```

### Text Reports
```bash
# Full test results
less qa_reports/test_results_full.txt

# Failures only
less qa_reports/failures.txt

# Summary
cat qa_reports/ASSESSMENT_SUMMARY.md
```
EOF

echo "✅ Assessment summary saved to $OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
echo ""

echo "=================================================="
echo "✅ Quality Assessment Complete!"
echo "=================================================="
echo ""
echo "📊 Reports generated in: $OUTPUT_DIR/"
echo ""
echo "📖 Next steps:"
echo "1. Review the assessment summary:"
echo "   cat $OUTPUT_DIR/ASSESSMENT_SUMMARY.md"
echo ""
echo "2. View coverage reports:"
echo "   open $OUTPUT_DIR/coverage_run_agent/index.html"
echo "   open $OUTPUT_DIR/coverage_overall/index.html"
echo ""
echo "3. Review test failures:"
echo "   less $OUTPUT_DIR/test_results_full.txt"
echo ""
echo "4. Follow the Quality Assurance Plan:"
echo "   cat QUALITY_ASSURANCE_PLAN.md"
echo ""
echo "5. Track progress with TODO checklist:"
echo "   cat TODO.md"
echo ""
