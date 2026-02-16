#!/bin/bash
# Monitor data fetch progress

LOG_FILE="data/historical/curriculum_2020_2023/fetch_log.txt"

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Log file not found: $LOG_FILE"
    exit 1
fi

echo "================================================================================"
echo "DATA FETCH PROGRESS MONITOR"
echo "================================================================================"
echo ""

# Get last 3 lines
echo "📊 Latest Progress:"
tail -3 "$LOG_FILE"
echo ""

# Count total chunks fetched
CHUNKS=$(grep -c "Chunk" "$LOG_FILE" 2>/dev/null || echo "0")
echo "✅ Total Chunks Fetched: $CHUNKS"

# Estimate progress (rough)
# Assuming ~1461 chunks per pair/timeframe for 4 years
# 4 pairs × 3 timeframes = 12 datasets
# ~1461 × 12 = ~17,532 total chunks expected
TOTAL_EXPECTED=17532
PROGRESS=$(echo "scale=2; ($CHUNKS / $TOTAL_EXPECTED) * 100" | bc 2>/dev/null || echo "0")
echo "📈 Estimated Overall Progress: ${PROGRESS}%"

# Count completed datasets (files saved)
PARQUET_FILES=$(ls data/historical/curriculum_2020_2023/*.parquet 2>/dev/null | wc -l | tr -d ' ')
echo "💾 Datasets Completed: ${PARQUET_FILES} / 12"

# Check if process is still running
if pgrep -f "fetch_curriculum_data.py" > /dev/null; then
    echo "🔄 Status: RUNNING"
else
    echo "⚠️  Status: NOT RUNNING"
fi

echo ""
echo "================================================================================"

# Show file sizes if any exist
if [ "$PARQUET_FILES" -gt 0 ]; then
    echo ""
    echo "📂 Completed Data Files:"
    ls -lh data/historical/curriculum_2020_2023/*.parquet 2>/dev/null | awk '{print "   " $9 " - " $5}'
fi
