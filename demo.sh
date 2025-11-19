#!/bin/bash

echo "=================================================="
echo "Finance Feedback Engine 2.0 - Feature Demo"
echo "=================================================="
echo ""

echo "1. Engine Status Check"
echo "----------------------"
python main.py -c config/config.test.yaml status
echo ""

echo "2. Analyze Bitcoin (BTCUSD)"
echo "---------------------------"
python main.py -c config/config.test.yaml analyze BTCUSD
echo ""

echo "3. Analyze Ethereum (ETHUSD)"
echo "----------------------------"
python main.py -c config/config.test.yaml analyze ETHUSD
echo ""

echo "4. Check Account Balance"
echo "------------------------"
python main.py -c config/config.test.yaml balance
echo ""

echo "5. View Decision History"
echo "------------------------"
python main.py -c config/config.test.yaml history --limit 5
echo ""

echo "=================================================="
echo "Demo Complete!"
echo "=================================================="
