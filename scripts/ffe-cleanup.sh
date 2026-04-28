#!/bin/bash
# FFE Server Cleanup / Hygiene Audit Script
# Default mode is non-destructive audit. Use --apply to perform cleanup.
#
# Usage:
#   ./scripts/ffe-cleanup.sh            # audit only (default)
#   ./scripts/ffe-cleanup.sh --dry-run  # explicit audit / preview
#   ./scripts/ffe-cleanup.sh --apply    # perform safe cleanup actions

set -euo pipefail

MODE="audit"
for arg in "$@"; do
  case "$arg" in
    --apply) MODE="apply" ;;
    --dry-run|--audit) MODE="audit" ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

APPLY=false
[[ "$MODE" == "apply" ]] && APPLY=true

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
section() { printf '\n'; log "=== $* ==="; }
run_or_preview() {
  local msg="$1"
  shift
  if $APPLY; then
    log "$msg"
    "$@"
  else
    log "[AUDIT] Would run: $msg"
  fi
}

section "Mode"
log "Mode: $MODE"
log "Cleanup is operator-gated; destructive actions only run with --apply"

section "Docker Build Cache"
BUILD_CACHE_LINE=$(docker system df 2>/dev/null | awk '/Build Cache/ {print $0}' || true)
log "Build cache summary: ${BUILD_CACHE_LINE:-unavailable}"
run_or_preview "Prune Docker build cache older than 7 days" docker builder prune --filter until=168h -f

section "Docker Images"
DANGLING_COUNT=$(docker images -f dangling=true -q | wc -l | tr -d ' ')
log "Dangling image count: $DANGLING_COUNT"
log "Top dangling images by size:"
docker images --filter dangling=true --format '  {{.ID}} {{.Repository}}:{{.Tag}} {{.Size}} {{.CreatedSince}}' | head -20 || true
if [[ "$DANGLING_COUNT" != "0" ]]; then
  run_or_preview "Prune dangling Docker images" docker image prune -f
fi

section "Old / Exited Containers"
EXITED_CONTAINERS=$(docker ps -a --filter status=exited --format '{{.Names}} {{.Image}} {{.Status}}')
if [[ -n "$EXITED_CONTAINERS" ]]; then
  echo "$EXITED_CONTAINERS" | sed 's/^/  /'
  MANUAL_EXITED=$(docker ps -a --filter status=exited --format '{{.Names}}' | grep '^ffe-backend-manual-' || true)
  if [[ -n "$MANUAL_EXITED" ]]; then
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      run_or_preview "Remove exited manual container $name" docker rm -f "$name"
    done <<< "$MANUAL_EXITED"
  fi
else
  log "No exited containers found"
fi

section "Docker Volumes"
log "Volume inventory:"
docker volume ls --format '  {{.Name}}' | while read -r vol; do
  [[ -z "$vol" ]] && continue
  size=$(docker system df -v 2>/dev/null | awk -v v="$vol" '$1==v {print $(NF)}' | head -1)
  printf '  %s %s\n' "$vol" "${size:-unknown}"
done || true
DANGLING_VOLUMES=$(docker volume ls -f dangling=true -q | wc -l | tr -d ' ')
log "Dangling volume count: $DANGLING_VOLUMES"
if [[ "$DANGLING_VOLUMES" != "0" ]]; then
  run_or_preview "Prune dangling Docker volumes" docker volume prune -f
fi

section "FFE Runtime Artifacts"
for pair in \
  "/home/cmp6510/finance_feedback_engine/logs logs" \
  "/home/cmp6510/finance_feedback_engine/data data" \
  "/home/cmp6510/finance_feedback_engine/backups backups" \
  "/home/cmp6510/finance_feedback_engine/build build"; do
  target=${pair%% *}
  label=${pair##* }
  if [[ -d "$target" ]]; then
    size=$(du -sh "$target" 2>/dev/null | awk '{print $1}')
    count=$(find "$target" -type f 2>/dev/null | wc -l | tr -d ' ')
    log "$label: $size across $count files"
  else
    log "$label: missing"
  fi
done

section "FFE Decision / Data Retention Preview"
DECISIONS_DIR="/home/cmp6510/finance_feedback_engine/data/decisions"
if [[ -d "$DECISIONS_DIR" ]]; then
  old_decisions=$(find "$DECISIONS_DIR" -name '*.json' -mtime +14 | wc -l | tr -d ' ')
  bak_files=$(find "$DECISIONS_DIR" -name '*.bak' | wc -l | tr -d ' ')
  log "Decision files older than 14 days: $old_decisions"
  log "Decision backup (.bak) files: $bak_files"
  log "Data cleanup is intentionally preview-only in this script revision"
fi

section "Scratch / Worktree Cleanup"
for d in /home/cmp6510/finance_feedback_engine_cov_* /home/cmp6510/finance_feedback_engine_scratch_* /home/cmp6510/finance_feedback_engine_observability_*; do
  if [[ -d "$d" ]]; then
    size=$(du -sh "$d" 2>/dev/null | awk '{print $1}')
    log "Scratch dir candidate: $d ($size)"
    run_or_preview "Remove scratch dir $d" rm -rf "$d"
  fi
done

section "Post-Run Summary"
df -h / | awk 'NR==2 {print "Disk: " $3 " / " $2 " (" $5 ")"}'
docker system df 2>/dev/null | head -5
log "Done."
