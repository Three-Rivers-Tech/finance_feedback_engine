#!/bin/bash
# Finance Feedback Engine - Restore Script
# Usage: ./scripts/restore.sh [backup-timestamp]
# Example: ./scripts/restore.sh 20250127-143022

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKUP_ID=${1:-}
BACKUP_DIR="./backups"

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Show usage if no backup ID provided
if [ -z "$BACKUP_ID" ]; then
    echo "Usage: $0 <backup-timestamp>"
    echo ""
    echo "Available backups:"

    if [ -d "$BACKUP_DIR" ]; then
        find "$BACKUP_DIR" -maxdepth 1 -name "backup-*" -type d | sort -r | while read backup; do
            TIMESTAMP=$(basename "$backup" | sed 's/backup-//')
            SIZE=$(du -sh "$backup" | cut -f1)
            echo "  - $TIMESTAMP (Size: $SIZE)"
        done
    else
        echo "  No backups found"
    fi

    exit 1
fi

# Construct backup path
BACKUP_PATH="${BACKUP_DIR}/backup-${BACKUP_ID}"

if [ ! -d "$BACKUP_PATH" ]; then
    log_error "Backup not found: $BACKUP_PATH"
    exit 1
fi

log_info "Restore Configuration:"
log_info "  Backup ID: $BACKUP_ID"
log_info "  Backup Path: $BACKUP_PATH"
echo ""

# Warning
log_warn "⚠️  WARNING: This will replace current data with backup data"
log_warn "⚠️  Make sure services are stopped before restoring"
echo ""

# Confirm
read -p "Do you want to continue? (yes/no): " -r
echo
if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    log_info "Restore cancelled"
    exit 0
fi

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    log_error "Services are still running. Stop them first with: ./scripts/deploy.sh production stop"
    exit 1
fi

log_info "✅ Services are stopped, proceeding with restore..."

# Restore Docker volumes
log_info "Restoring Docker volumes..."

# Data volume
if [ -f "${BACKUP_PATH}/data.tar.gz" ]; then
    log_info "  Restoring ffe-data volume..."
    docker volume create ffe-data > /dev/null 2>&1 || true
    docker run --rm \
        -v ffe-data:/data \
        -v "$(pwd)/${BACKUP_PATH}:/backup:ro" \
        alpine sh -c "rm -rf /data/* && tar xzf /backup/data.tar.gz -C /data"
    log_info "  ✅ Data volume restored"
else
    log_warn "  data.tar.gz not found, skipping"
fi

# Logs volume
if [ -f "${BACKUP_PATH}/logs.tar.gz" ]; then
    log_info "  Restoring ffe-logs volume..."
    docker volume create ffe-logs > /dev/null 2>&1 || true
    docker run --rm \
        -v ffe-logs:/logs \
        -v "$(pwd)/${BACKUP_PATH}:/backup:ro" \
        alpine sh -c "rm -rf /logs/* && tar xzf /backup/logs.tar.gz -C /logs"
    log_info "  ✅ Logs volume restored"
else
    log_warn "  logs.tar.gz not found, skipping"
fi

# Prometheus data
if [ -f "${BACKUP_PATH}/prometheus.tar.gz" ]; then
    log_info "  Restoring prometheus-data volume..."
    docker volume create prometheus-data > /dev/null 2>&1 || true
    docker run --rm \
        -v prometheus-data:/prometheus \
        -v "$(pwd)/${BACKUP_PATH}:/backup:ro" \
        alpine sh -c "rm -rf /prometheus/* && tar xzf /backup/prometheus.tar.gz -C /prometheus"
    log_info "  ✅ Prometheus data restored"
else
    log_warn "  prometheus.tar.gz not found, skipping"
fi

# Grafana data
if [ -f "${BACKUP_PATH}/grafana.tar.gz" ]; then
    log_info "  Restoring grafana-data volume..."
    docker volume create grafana-data > /dev/null 2>&1 || true
    docker run --rm \
        -v grafana-data:/grafana \
        -v "$(pwd)/${BACKUP_PATH}:/backup:ro" \
        alpine sh -c "rm -rf /grafana/* && tar xzf /backup/grafana.tar.gz -C /grafana"
    log_info "  ✅ Grafana data restored"
else
    log_warn "  grafana.tar.gz not found, skipping"
fi

# Restore configuration files
if [ -d "${BACKUP_PATH}/config" ]; then
    log_info "Restoring configuration files..."
    cp -r "${BACKUP_PATH}/config"/* config/ 2>/dev/null || true
    log_info "  ✅ Config files restored"
fi

# Restore database (if exists)
if [ -f "${BACKUP_PATH}/database.sql" ]; then
    log_warn "Database backup found but not restored automatically"
    log_info "To restore PostgreSQL database:"
    log_info "  1. Start services: ./scripts/deploy.sh production start"
    log_info "  2. Run: docker-compose exec -T postgres psql -U <user> <dbname> < ${BACKUP_PATH}/database.sql"
fi

# Summary
echo ""
log_info "📦 Restore Summary:"
echo "  Status: ✅ Complete"
echo "  Backup ID: $BACKUP_ID"
echo "  Restored from: $BACKUP_PATH"
echo ""
log_info "🚀 Start services with: ./scripts/deploy.sh production start"
echo ""
log_warn "NOTE: Review logs after starting to ensure everything works correctly"

exit 0
