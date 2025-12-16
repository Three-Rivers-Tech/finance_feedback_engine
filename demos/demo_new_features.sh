#!/bin/bash
echo "=========================================================================="
echo "Finance Feedback Engine 2.0 - NEW FEATURES DEMO"
echo "=========================================================================="
echo ""
echo "This demo showcases the latest features added to the engine:"
echo "  1. News Sentiment Analysis"
echo "  2. Macroeconomic Indicators"
echo "  3. Dynamic Weight Adjustment for Ensemble"
echo "  4. Enhanced Portfolio Tracking"
echo ""
echo "=========================================================================="
echo ""

echo "📊 DEMO 1: Sentiment Analysis & Macroeconomic Indicators"
echo "----------------------------------------------------------------------"
echo "Shows how the engine enriches decisions with news sentiment and macro data"
echo ""
python examples/sentiment_macro_example.py
echo ""
echo "Press Enter to continue..."
read

echo ""
echo "🔄 DEMO 2: Dynamic Weight Adjustment (Ensemble Resilience)"
echo "----------------------------------------------------------------------"
echo "Shows how ensemble mode handles provider failures gracefully"
echo ""
python examples/dynamic_weight_adjustment_example.py
echo ""
echo "Press Enter to continue..."
read

echo ""
echo "💼 DEMO 3: Portfolio Tracking with Oanda (Forex)"
echo "----------------------------------------------------------------------"
echo "Shows detailed portfolio breakdown for forex trading"
echo ""
python examples/oanda_forex_example.py
echo ""
echo "Press Enter to continue..."
read

echo ""
echo "📈 DEMO 4: Position Sizing Example"
echo "----------------------------------------------------------------------"
echo "Shows how the engine calculates position sizes with risk management"
echo ""
python examples/position_sizing_example.py
echo ""

echo "=========================================================================="
echo "✅ NEW FEATURES DEMO COMPLETE!"
echo "=========================================================================="
echo ""
echo "For more information, see:"
echo "  - docs/ENSEMBLE_SYSTEM.md (ensemble mode)"
echo "  - docs/DYNAMIC_WEIGHT_ADJUSTMENT.md (failure handling)"
echo "  - SENTIMENT_MACRO_FEATURES.md (market context)"
echo "  - docs/PORTFOLIO_TRACKING.md (portfolio details)"
echo ""
