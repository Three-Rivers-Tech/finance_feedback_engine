#!/bin/bash
# Automatic launcher for Level 1 optimization when data is ready

set -e

REPO_DIR="$HOME/finance_feedback_engine"
DATA_DIR="$REPO_DIR/data/historical/curriculum_2020_2023"
LOG_FILE="$DATA_DIR/fetch_log.txt"
COMPLETION_MARKER="$DATA_DIR/.fetch_complete"

cd "$REPO_DIR"

echo "================================================================================"
echo "AUTO-LAUNCH MONITOR FOR LEVEL 1 OPTIMIZATION"
echo "================================================================================"
echo "Started: $(date)"
echo ""

# Function to check if data fetch is complete
check_completion() {
    # Check for completion marker file
    if [ -f "$COMPLETION_MARKER" ]; then
        return 0
    fi
    
    # Check if acquisition_summary.csv exists (indicates completion)
    if [ -f "$DATA_DIR/acquisition_summary.csv" ]; then
        touch "$COMPLETION_MARKER"
        return 0
    fi
    
    # Check if process is still running
    if ! pgrep -f "fetch_curriculum_data.py" > /dev/null; then
        # Process not running - check if we have data
        PARQUET_COUNT=$(ls "$DATA_DIR"/*.parquet 2>/dev/null | wc -l | tr -d ' ')
        if [ "$PARQUET_COUNT" -ge 10 ]; then
            # We have most of the data, assume complete
            touch "$COMPLETION_MARKER"
            return 0
        fi
    fi
    
    return 1
}

# Function to validate data
validate_data() {
    echo "📊 Validating acquired data..."
    
    PARQUET_COUNT=$(ls "$DATA_DIR"/*.parquet 2>/dev/null | wc -l | tr -d ' ')
    echo "   Parquet files found: $PARQUET_COUNT"
    
    if [ "$PARQUET_COUNT" -lt 6 ]; then
        echo "   ⚠️  Warning: Only $PARQUET_COUNT files (expected 12)"
        echo "   Proceeding anyway with available data..."
    else
        echo "   ✅ Sufficient data files present"
    fi
    
    # Check if acquisition summary exists
    if [ -f "$DATA_DIR/acquisition_summary.csv" ]; then
        echo "   ✅ Acquisition summary found"
        echo ""
        echo "   Summary contents:"
        cat "$DATA_DIR/acquisition_summary.csv" | head -15
    fi
    
    return 0
}

# Function to launch Level 1 optimization
launch_level1() {
    echo ""
    echo "================================================================================"
    echo "LAUNCHING LEVEL 1 OPTIMIZATION"
    echo "================================================================================"
    echo "Time: $(date)"
    echo ""
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Create log directory
    mkdir -p optimization_results/level_1
    
    # Launch optimization in background
    nohup python -u scripts/curriculum_optimizer.py --level 1 \
        > optimization_results/level_1/optimization_live.log 2>&1 &
    
    PID=$!
    echo "✅ Level 1 optimization launched!"
    echo "   PID: $PID"
    echo "   Log: optimization_results/level_1/optimization_live.log"
    echo ""
    echo "Monitor progress:"
    echo "   tail -f optimization_results/level_1/optimization_live.log"
    echo ""
    echo "================================================================================"
}

# Main monitoring loop
echo "⏳ Waiting for data acquisition to complete..."
echo "   Checking every 5 minutes..."
echo ""

CHECK_COUNT=0
while true; do
    CHECK_COUNT=$((CHECK_COUNT + 1))
    
    if check_completion; then
        echo ""
        echo "✅ Data acquisition complete! (Check #$CHECK_COUNT)"
        echo ""
        
        validate_data
        
        # Check if Level 1 is already running
        if pgrep -f "curriculum_optimizer.py --level 1" > /dev/null; then
            echo "⚠️  Level 1 optimization already running - exiting monitor"
            exit 0
        fi
        
        launch_level1
        exit 0
    else
        # Show progress every 5 checks (25 minutes)
        if [ $((CHECK_COUNT % 5)) -eq 0 ]; then
            echo "[$(date +%H:%M)] Check #$CHECK_COUNT - Still waiting..."
            if [ -f "$LOG_FILE" ]; then
                CHUNKS=$(grep -c "Chunk" "$LOG_FILE" 2>/dev/null || echo "0")
                echo "   Chunks fetched so far: $CHUNKS"
            fi
        fi
    fi
    
    # Wait 5 minutes before next check
    sleep 300
done
