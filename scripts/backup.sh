#!/bin/bash
# Finance Feedback Engine - Backup Script
# Usage: ./scripts/backup.sh [environment]
# Example: ./scripts/backup.sh production

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/backup-${TIMESTAMP}"
RETENTION_DAYS=30

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

# Create backup directory
mkdir -p "$BACKUP_PATH"

log_info "Backup Configuration:"
log_info "  Environment: $ENVIRONMENT"
log_info "  Backup Path: $BACKUP_PATH"
log_info "  Timestamp: $TIMESTAMP"
echo ""

# Backup metadata
cat > "${BACKUP_PATH}/metadata.txt" <<EOF
Finance Feedback Engine Backup
Generated: $(date)
Environment: $ENVIRONMENT
Hostname: $(hostname)
Git Commit: $(git rev-parse HEAD 2>/dev/null || echo "N/A")
Git Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")
EOF

log_info "Created backup metadata"

# Backup Docker volumes
log_info "Backing up Docker volumes..."

# Data volume
if docker volume inspect ffe-data > /dev/null 2>&1; then
    log_info "  Backing up ffe-data volume..."
    docker run --rm \
        -v ffe-data:/data:ro \
        -v "$(pwd)/${BACKUP_PATH}:/backup" \
        alpine tar czf /backup/data.tar.gz -C /data .
    log_info "  ✅ Data volume backed up ($(du -sh ${BACKUP_PATH}/data.tar.gz | cut -f1))"
else
    log_warn "  ffe-data volume not found, skipping"
fi

# Logs volume
if docker volume inspect ffe-logs > /dev/null 2>&1; then
    log_info "  Backing up ffe-logs volume..."
    docker run --rm \
        -v ffe-logs:/logs:ro \
        -v "$(pwd)/${BACKUP_PATH}:/backup" \
        alpine tar czf /backup/logs.tar.gz -C /logs .
    log_info "  ✅ Logs volume backed up ($(du -sh ${BACKUP_PATH}/logs.tar.gz | cut -f1))"
else
    log_warn "  ffe-logs volume not found, skipping"
fi

# Prometheus data
if docker volume inspect prometheus-data > /dev/null 2>&1; then
    log_info "  Backing up prometheus-data volume..."
    docker run --rm \
        -v prometheus-data:/prometheus:ro \
        -v "$(pwd)/${BACKUP_PATH}:/backup" \
        alpine tar czf /backup/prometheus.tar.gz -C /prometheus .
    log_info "  ✅ Prometheus data backed up ($(du -sh ${BACKUP_PATH}/prometheus.tar.gz | cut -f1))"
else
    log_warn "  prometheus-data volume not found, skipping"
fi

# Grafana data
if docker volume inspect grafana-data > /dev/null 2>&1; then
    log_info "  Backing up grafana-data volume..."
    docker run --rm \
        -v grafana-data:/grafana:ro \
        -v "$(pwd)/${BACKUP_PATH}:/backup" \
        alpine tar czf /backup/grafana.tar.gz -C /grafana .
    log_info "  ✅ Grafana data backed up ($(du -sh ${BACKUP_PATH}/grafana.tar.gz | cut -f1))"
else
    log_warn "  grafana-data volume not found, skipping"
fi

# Backup configuration files
log_info "Backing up configuration files..."
mkdir -p "${BACKUP_PATH}/config"

if [ -d "config" ]; then
    cp -r config/* "${BACKUP_PATH}/config/" 2>/dev/null || true
    log_info "  ✅ Config directory backed up"
fi

# Backup environment files (sanitized - remove sensitive values)
for env_file in .env .env.production .env.staging .env.dev; do
    if [ -f "$env_file" ]; then
        # Create sanitized copy (replace values with ****)
        sed 's/=.*/=****/' "$env_file" > "${BACKUP_PATH}/${env_file}.sanitized" 2>/dev/null || true
        log_info "  ✅ ${env_file} backed up (sanitized)"
    fi
done

# Backup docker-compose files
for compose_file in docker-compose.yml docker-compose.*.yml; do
    if [ -f "$compose_file" ]; then
        cp "$compose_file" "${BACKUP_PATH}/" 2>/dev/null || true
        log_info "  ✅ ${compose_file} backed up"
    fi
done

# Database backup (if PostgreSQL is running)
if docker-compose ps | grep -q postgres; then
    log_info "Backing up PostgreSQL database..."
    ENV_FILE=".env.${ENVIRONMENT}"

    # Extract database name from environment file
    if [ -f "$ENV_FILE" ]; then
        DB_NAME=$(grep -E "^POSTGRES_DB=" "$ENV_FILE" | cut -d= -f2 || echo "ffe")
        DB_USER=$(grep -E "^POSTGRES_USER=" "$ENV_FILE" | cut -d= -f2 || echo "ffe_user")

        docker-compose exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" \
            > "${BACKUP_PATH}/database.sql" 2>/dev/null && \
            log_info "  ✅ PostgreSQL database backed up ($(du -sh ${BACKUP_PATH}/database.sql | cut -f1))" || \
            log_warn "  PostgreSQL backup failed (service may not be running)"
    fi
else
    log_info "PostgreSQL not running, skipping database backup"
fi

# Create backup manifest
log_info "Creating backup manifest..."
cat > "${BACKUP_PATH}/MANIFEST.txt" <<EOF
Finance Feedback Engine Backup Manifest
========================================
Backup Date: $(date)
Environment: $ENVIRONMENT
Backup ID: ${TIMESTAMP}

Contents:
EOF

find "${BACKUP_PATH}" -type f -exec basename {} \; | sort | while read file; do
    echo "  - $file" >> "${BACKUP_PATH}/MANIFEST.txt"
done

# Calculate total backup size
BACKUP_SIZE=$(du -sh "$BACKUP_PATH" | cut -f1)

# Cleanup old backups
log_info "Cleaning up old backups (retention: ${RETENTION_DAYS} days)..."
DELETED_COUNT=0
if [ -d "$BACKUP_DIR" ]; then
    while IFS= read -r old_backup; do
        rm -rf "$old_backup"
        DELETED_COUNT=$((DELETED_COUNT + 1))
    done < <(find "$BACKUP_DIR" -maxdepth 1 -name "backup-*" -type d -mtime +${RETENTION_DAYS})

    if [ $DELETED_COUNT -gt 0 ]; then
        log_info "  ✅ Deleted $DELETED_COUNT old backup(s)"
    else
        log_info "  No old backups to delete"
    fi
fi

# Summary
echo ""
log_info "📦 Backup Summary:"
echo "  Status: ✅ Complete"
echo "  Location: $BACKUP_PATH"
echo "  Size: $BACKUP_SIZE"
echo "  Files: $(find ${BACKUP_PATH} -type f | wc -l)"
echo ""
log_info "📋 Restore this backup with: ./scripts/restore.sh ${TIMESTAMP}"
echo ""

# Create latest symlink
ln -sfn "backup-${TIMESTAMP}" "${BACKUP_DIR}/latest"
log_info "Updated 'latest' symlink"

exit 0
