"""Write a local .env template with placeholder values only.

This helper intentionally contains no real credentials.
Populate the generated .env manually or via a secret manager.
"""

from pathlib import Path

env_content = """# Placeholder values only. Replace locally.
COINBASE_API_KEY=YOUR_COINBASE_API_KEY
COINBASE_API_SECRET=YOUR_COINBASE_API_SECRET
OANDA_API_KEY=YOUR_OANDA_API_KEY
OANDA_ACCOUNT_ID=YOUR_OANDA_ACCOUNT_ID
OANDA_ENVIRONMENT=practice
ALPHA_VANTAGE_API_KEY=YOUR_ALPHA_VANTAGE_API_KEY
COINBASE_USE_SANDBOX=false
OLLAMA_HOST=http://127.0.0.1:11434
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=ffe_user
POSTGRES_PASSWORD=ffe_pass
POSTGRES_DB=ffe
FINANCE_FEEDBACK_API_KEY=local-dev-key
LOGGING_LEVEL=INFO
MONITORING_ENABLED=true
RUN_OANDA_KELLY=false
"""

Path('.env').write_text(env_content)
print('Wrote .env template with placeholder values only')
