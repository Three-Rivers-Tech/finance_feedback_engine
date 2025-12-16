#!/usr/bin/env python3
"""Start ngrok tunnel and get public URL."""

import sys
import tempfile
import time
from pathlib import Path

import yaml
from pyngrok import ngrok

# Load auth token from config
config_path = Path(__file__).parent / "config" / "config.local.yaml"
with open(config_path) as f:
    config = yaml.safe_load(f)
    auth_token = config.get("telegram", {}).get("ngrok_auth_token")
    if not auth_token:
        print("❌ Error: ngrok_auth_token not found in config/config.local.yaml")
        sys.exit(1)

# Set auth token
ngrok.set_auth_token(auth_token)

# Start ngrok tunnel to port 8000
print("🔌 Starting ngrok tunnel to port 8000...")
try:
    # Start the tunnel
    tunnel = ngrok.connect(8000, bind_tls=True)

    # Get the public URL
    public_url = tunnel.public_url

    print(f"\n✅ Ngrok tunnel started successfully!")
    print(f"📡 Public URL: {public_url}")
    print(f"🔗 Webhook endpoint: {public_url}/webhook/telegram")
    print("\nPress Ctrl+C to stop the tunnel...")

    # Write URL to file in a secure temporary location
    ngrok_url_path = Path(tempfile.mktemp(prefix="ngrok_url_", suffix=".txt"))
    with open(ngrok_url_path, "w") as f:
        f.write(public_url)
    print(f"🔗 URL saved to: {ngrok_url_path}")

    # Keep the tunnel alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping ngrok tunnel...")
        ngrok.kill()

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
