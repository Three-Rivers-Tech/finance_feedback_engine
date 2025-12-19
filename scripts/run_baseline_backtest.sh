#!/bin/bash
# scripts/run_baseline_backtest.sh
# Run baseline backtest and save results for regression detection

set -e

ASSET="${1:-BTCUSD}"
START_DATE="${2:-2024-01-01}"
END_DATE="${3:-2024-06-01}"
OUTPUT_DIR="data/baseline_results"

mkdir -p "$OUTPUT_DIR"

echo "🎯 Running baseline backtest"
echo "   Asset: $ASSET"
echo "   Period: $START_DATE to $END_DATE"
echo ""

# Run backtest with all features DISABLED (baseline)
python main.py backtest "$ASSET" \
    --start-date "$START_DATE" \
    --end-date "$END_DATE" \
    --output-json "${OUTPUT_DIR}/baseline_${ASSET}_$(date +%Y%m%d).json"

echo ""
echo "✅ Baseline results saved to: ${OUTPUT_DIR}/baseline_${ASSET}_$(date +%Y%m%d).json"
echo ""
echo "Use this for regression detection:"
echo "  python scripts/compare_performance.py \\"
echo "    --baseline ${OUTPUT_DIR}/baseline_${ASSET}_$(date +%Y%m%d).json \\"
echo "    --current <path_to_new_results.json>"
