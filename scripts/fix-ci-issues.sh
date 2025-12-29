#!/bin/bash
# Quick script to fix the CI issues

echo "🔧 Fixing CI code quality issues..."

# Fix f-string issues (convert unnecessary f-strings to regular strings)
echo "Fixing f-string issues..."

# demo.py
sed -i 's/f"Trading engine started successfully"/\
"Trading engine started successfully"/g' \
finance_feedback_engine/cli/commands/demo.py

sed -i 's/f"Trading engine stopped"/\
"Trading engine stopped"/g' \
finance_feedback_engine/cli/commands/demo.py

# frontend.py
sed -i 's/f"Starting frontend setup..."/\
"Starting frontend setup..."/g' \
finance_feedback_engine/cli/commands/frontend.py

sed -i 's/f"Frontend dependencies installed successfully"/\
"Frontend dependencies installed successfully"/g' \
finance_feedback_engine/cli/commands/frontend.py

sed -i 's/f"Frontend build completed successfully"/\
"Frontend build completed successfully"/g' \
finance_feedback_engine/cli/commands/frontend.py

sed -i 's/f"Frontend cleaned successfully"/\
"Frontend cleaned successfully"/g' \
finance_feedback_engine/cli/commands/frontend.py

echo "✅ F-string issues fixed"

echo "🎉 Done! Run 'git diff' to review changes"
