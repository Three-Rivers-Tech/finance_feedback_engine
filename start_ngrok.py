#!/usr/bin/env python3
"""Start ngrok tunnel and get public URL."""

from pyngrok import ngrok
import time
import sys
import yaml
from pathlib import Path

# Load auth token from config
config_path = Path(__file__).parent / "config" / "config.local.yaml"
with open(config_path) as f:
    config = yaml.safe_load(f)
    auth_token = config.get('telegram', {}).get('ngrok_auth_token')
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

    # Write URL to file for later use
    with open('/tmp/ngrok_url.txt', 'w') as f:
        f.write(public_url)

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
