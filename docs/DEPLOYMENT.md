# Deployment Guide

Complete guide for deploying the Finance Feedback Engine in production and development environments.

## 📋 Table of Contents

1. [Environment Variables](#environment-variables)
2. [Docker Deployment](#docker-deployment)
3. [Cloud Deployment](#cloud-deployment)
4. [Configuration Management](#configuration-management)
5. [Security Best Practices](#security-best-practices)
6. [Monitoring & Logging](#monitoring--logging)

## Environment Variables

### Required Variables

The following environment variables must be set for the engine to function:

#### Market Data Provider
```bash
# Alpha Vantage API (Premium recommended for production)
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key
```

#### Trading Platforms

**Coinbase Advanced Trade:**
```bash
COINBASE_API_KEY=your_coinbase_api_key
COINBASE_API_SECRET=your_coinbase_api_secret
COINBASE_PASSPHRASE=your_coinbase_passphrase  # Optional for some accounts
```

**Oanda Forex:**
```bash
OANDA_API_KEY=your_oanda_api_key
OANDA_ACCOUNT_ID=your_oanda_account_id
OANDA_ENVIRONMENT=practice  # or 'live' for production
```

### Optional Variables

#### AI Providers

**OpenAI:**
```bash
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4  # or gpt-3.5-turbo
```

**Anthropic:**
```bash
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=claude-3-opus-20240229  # or other Claude models
```

**Google Gemini:**
```bash
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-pro
```

#### Web Service & Integrations (Optional)

**Redis:**
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password  # If authentication enabled
REDIS_DB=0
```

**Telegram Bot:**
```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
TELEGRAM_ADMIN_USER_ID=your_telegram_user_id
```

**Ngrok (Development only):**
```bash
NGROK_AUTH_TOKEN=your_ngrok_auth_token
```

#### Application Configuration

```bash
# Trading platform selection
TRADING_PLATFORM=coinbase  # or 'oanda', 'mock'

# AI provider selection
AI_PROVIDER=ensemble  # or 'local', 'openai', 'anthropic', 'cli', 'codex', 'qwen'

# Risk management
MAX_DRAWDOWN=0.20
MAX_POSITION_SIZE=0.30
VAR_LIMIT=0.05

# Data directories (optional, defaults provided)
DATA_DIR=/app/data
DECISIONS_DIR=/app/data/decisions
MEMORY_DIR=/app/data/memory

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=/app/logs/engine.log
```

## Docker Deployment

### Dockerfile

A basic `Dockerfile` for the Finance Feedback Engine:

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install package in development mode
RUN pip install -e .

# Create data directories
RUN mkdir -p /app/data/decisions /app/data/memory /app/logs

# Expose port for web service (if enabled)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "from finance_feedback_engine.core import FinanceFeedbackEngine; print('OK')" || exit 1

# Default command (can be overridden)
CMD ["python", "main.py", "status"]
```

### Docker Compose

For multi-service deployments with Redis:

```yaml
version: '3.8'

services:
  engine:
    build: .
    container_name: finance_feedback_engine
    environment:
      # Load from .env file
      - ALPHA_VANTAGE_API_KEY=${ALPHA_VANTAGE_API_KEY}
      - COINBASE_API_KEY=${COINBASE_API_KEY}
      - COINBASE_API_SECRET=${COINBASE_API_SECRET}
      - OANDA_API_KEY=${OANDA_API_KEY}
      - OANDA_ACCOUNT_ID=${OANDA_ACCOUNT_ID}
      - TRADING_PLATFORM=${TRADING_PLATFORM:-mock}
      - AI_PROVIDER=${AI_PROVIDER:-ensemble}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - ./logs:/app/logs
    depends_on:
      - redis
    restart: unless-stopped
    command: python main.py run-agent

  redis:
    image: redis:7-alpine
    container_name: finance_feedback_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes

  web:
    build: .
    container_name: finance_feedback_web
    environment:
      # Same environment variables as engine
      - ALPHA_VANTAGE_API_KEY=${ALPHA_VANTAGE_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    ports:
      - "8000:8000"
    depends_on:
      - redis
    restart: unless-stopped
    command: python main.py serve --port 8000

volumes:
  redis_data:
```

### Building and Running

```bash
# Create .env file with your credentials
cp .env.example .env
# Edit .env with your API keys

# Build image
docker build -t finance-feedback-engine .

# Run single container
docker run -d \
  --name finance-engine \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  finance-feedback-engine

# Run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f engine

# Stop services
docker-compose down
```

## Cloud Deployment

### AWS EC2

**Launch instance:**
```bash
# Use Ubuntu 22.04 LTS, t3.medium or larger
# Configure security group:
# - Port 22 (SSH)
# - Port 8000 (if using web service)
# - Port 6379 (Redis, internal only)
```

**Setup script:**
```bash
#!/bin/bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone repository
git clone https://github.com/Three-Rivers-Tech/finance_feedback_engine-2.0.git
cd finance_feedback_engine-2.0

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start services
docker-compose up -d
```

### Google Cloud Platform (GCP)

**Cloud Run deployment:**
```bash
# Build and push to Container Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/finance-engine

# Deploy to Cloud Run
gcloud run deploy finance-engine \
  --image gcr.io/YOUR_PROJECT_ID/finance-engine \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --set-env-vars ALPHA_VANTAGE_API_KEY=$ALPHA_VANTAGE_API_KEY,COINBASE_API_KEY=$COINBASE_API_KEY
```

### Azure Container Instances

```bash
# Create resource group
az group create --name finance-engine-rg --location eastus

# Create container
az container create \
  --resource-group finance-engine-rg \
  --name finance-engine \
  --image YOUR_REGISTRY/finance-engine:latest \
  --cpu 2 --memory 4 \
  --environment-variables \
    ALPHA_VANTAGE_API_KEY=$ALPHA_VANTAGE_API_KEY \
    COINBASE_API_KEY=$COINBASE_API_KEY \
  --restart-policy Always
```

## Configuration Management

### Configuration Hierarchy

The engine loads configuration in the following order (highest precedence first):

1. **Environment Variables** (highest priority)
2. `config/config.local.yaml` (user overrides, git-ignored)
3. `config/config.yaml` (defaults)

### Creating Production Configuration

```bash
# Copy default config
cp config/config.yaml config/config.local.yaml

# Edit with production settings
nano config/config.local.yaml
```

**Example production config:**
```yaml
# config/config.local.yaml
alpha_vantage_api_key: ${ALPHA_VANTAGE_API_KEY}

trading_platform: coinbase

platform_credentials:
  api_key: ${COINBASE_API_KEY}
  api_secret: ${COINBASE_API_SECRET}

ensemble:
  enabled_providers:
    - openai
    - anthropic
  provider_weights:
    openai: 0.6
    anthropic: 0.4
  two_phase_debate_enabled: true

risk:
  max_drawdown: 0.15
  max_position_size: 0.25
  var_limit: 0.04

monitoring:
  enabled: true
  manual_cli: false

agent:
  cycle_interval_seconds: 300
  max_daily_trades: 10
  kill_switch:
    enabled: true
    max_loss_percentage: 0.10
    max_gain_percentage: 0.50
```

### Secrets Management

**AWS Secrets Manager:**
```python
import boto3
import json

def get_secrets():
    client = boto3.client('secretsmanager', region_name='us-east-1')
    secret = client.get_secret_value(SecretId='finance-engine-prod')
    return json.loads(secret['SecretString'])

# In your code
secrets = get_secrets()
os.environ['ALPHA_VANTAGE_API_KEY'] = secrets['alpha_vantage_api_key']
```

**Kubernetes Secrets:**
```bash
# Create secret
kubectl create secret generic finance-engine-secrets \
  --from-literal=alpha-vantage-key=$ALPHA_VANTAGE_API_KEY \
  --from-literal=coinbase-key=$COINBASE_API_KEY

# Reference in deployment
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: engine
    env:
    - name: ALPHA_VANTAGE_API_KEY
      valueFrom:
        secretKeyRef:
          name: finance-engine-secrets
          key: alpha-vantage-key
```

## Security Best Practices

### 1. API Key Protection

- **Never commit API keys to git**
- Use environment variables or secrets management
- Rotate keys regularly (every 90 days)
- Use separate keys for development/staging/production

### 2. Network Security

```bash
# Firewall rules (UFW example)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 8000/tcp  # Web service (if needed)
sudo ufw enable
```

### 3. Docker Security

```dockerfile
# Run as non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Drop capabilities
RUN setcap 'cap_net_bind_service=+ep' /usr/local/bin/python
```

### 4. Data Encryption

- Enable encryption at rest for persistent volumes
- Use TLS for all API communications
- Encrypt Redis connection if using remote instance

### 5. Access Control

```yaml
# config/config.local.yaml
telegram:
  admin_user_ids:
    - 123456789  # Your Telegram user ID
  allowed_commands:
    - analyze
    - status
  # Restrict dangerous commands
  restricted_commands:
    - execute
    - run-agent
```

## Monitoring & Logging

### Application Logging

```yaml
# config/config.local.yaml
logging:
  level: INFO
  file: /app/logs/engine.log
  max_bytes: 10485760  # 10MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Prometheus Metrics (Optional)

```python
# Add to main.py or web service
from prometheus_client import start_http_server, Counter, Gauge

trades_total = Counter('trades_total', 'Total trades executed')
portfolio_value = Gauge('portfolio_value_usd', 'Current portfolio value')

# Start metrics server
start_http_server(9090)
```

### Health Checks

```python
# health_check.py
from finance_feedback_engine.core import FinanceFeedbackEngine

def health_check():
    try:
        engine = FinanceFeedbackEngine()
        balance = engine.get_balance()
        return {"status": "healthy", "balance": balance}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

### Log Aggregation

**ELK Stack (Elasticsearch, Logstash, Kibana):**
```yaml
# docker-compose.yml addition
  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
      - ./logs:/logs
```

**CloudWatch (AWS):**
```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Configure log collection
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json \
  -s
```

## Troubleshooting

### Common Issues

**1. API Rate Limits:**
```bash
# Check rate limit status
python main.py status

# Solution: Upgrade to premium API plan or reduce request frequency
```

**2. Docker Volume Permissions:**
```bash
# Fix permission issues
sudo chown -R 1000:1000 ./data ./logs
```

**3. Redis Connection Errors:**
```bash
# Check Redis connectivity
redis-cli -h redis ping

# Restart Redis
docker-compose restart redis
```

**4. Memory Issues:**
```bash
# Increase container memory limit
docker run --memory=4g --memory-swap=4g ...
```

### Debugging

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with verbose output
python main.py analyze BTCUSD -v

# Check container logs
docker logs finance-engine -f --tail 100
```

## Backup & Recovery

### Automated Backups

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups

# Backup decision history
tar -czf $BACKUP_DIR/decisions_$DATE.tar.gz data/decisions/

# Backup memory
tar -czf $BACKUP_DIR/memory_$DATE.tar.gz data/memory/

# Backup config
cp config/config.local.yaml $BACKUP_DIR/config_$DATE.yaml

# Keep last 7 days of backups
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

**Schedule with cron:**
```bash
# Run daily at 2 AM
0 2 * * * /app/backup.sh
```

## Performance Tuning

### Database Optimization

```python
# Use connection pooling for Redis
import redis
from redis.connection import ConnectionPool

pool = ConnectionPool(host='redis', port=6379, max_connections=10)
redis_client = redis.Redis(connection_pool=pool)
```

### Caching Strategy

```yaml
# config/config.local.yaml
caching:
  enabled: true
  ttl_seconds: 300  # 5 minutes
  max_entries: 1000
```

### Resource Limits

```yaml
# docker-compose.yml
services:
  engine:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Support & Documentation

- **Main Documentation**: [README.md](../README.md)
- **API Reference**: [API_REFERENCE.md](API_REFERENCE.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **GitHub Issues**: https://github.com/Three-Rivers-Tech/finance_feedback_engine-2.0/issues

## License

See [LICENSE](../LICENSE) file for details.
