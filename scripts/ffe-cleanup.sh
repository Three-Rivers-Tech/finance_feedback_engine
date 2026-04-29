#!/bin/bash
# FFE Server Cleanup / Hygiene Audit Script
# Default mode is non-destructive audit. Use --apply to perform cleanup.
#
# Usage:
#   ./scripts/ffe-cleanup.sh            # audit only (default)
#   ./scripts/ffe-cleanup.sh --dry-run  # explicit audit / preview
#   ./scripts/ffe-cleanup.sh --apply    # operator-approved cleanup
#
# Current scope:
# - --apply can prune build cache, dangling images, old tagged images, dangling volumes,
#   exited manual containers, old decision files, old .bak files, stale misc data files,
#   and scratch/worktree directories.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$REPO_ROOT/data"

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
OLD_TAGGED_IMAGES=$(docker images --format '{{.ID}} {{.Repository}}:{{.Tag}} {{.CreatedSince}}' \
  | grep -v 'finance_feedback_engine-backend:latest' \
  | grep -v 'postgres:16-alpine' \
  | grep -v '<none>' \
  | grep -E 'weeks|months' \
  | awk '{print $1}' || true)
OLD_TAGGED_COUNT=$(printf '%s\n' "$OLD_TAGGED_IMAGES" | sed '/^$/d' | wc -l | tr -d ' ')
log "Old tagged image candidates (weeks|months, excluding current backend/postgres): $OLD_TAGGED_COUNT"
if [[ "$DANGLING_COUNT" != "0" ]]; then
  run_or_preview "Prune dangling Docker images" docker image prune -f
fi
if [[ "$OLD_TAGGED_COUNT" != "0" ]]; then
  if $APPLY; then
    log "Removing old tagged images..."
    while IFS= read -r image_id; do
      [[ -z "$image_id" ]] && continue
      docker rmi -f "$image_id" 2>/dev/null || true
    done <<< "$OLD_TAGGED_IMAGES"
  else
    log "[AUDIT] Would remove $OLD_TAGGED_COUNT old tagged images"
  fi
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
docker system df -v | awk "
  /^Local Volumes space usage:/ {in_vols=1; next}
  /^Build cache usage:/ {in_vols=0}
  in_vols && /^VOLUME NAME/ {next}
  in_vols && NF >= 3 {printf \"  %s %s\\n\", \$1, \$NF}
" || true
DANGLING_VOLUMES=$(docker volume ls -f dangling=true -q | wc -l | tr -d ' ')
log "Dangling volume count: $DANGLING_VOLUMES"
if [[ "$DANGLING_VOLUMES" != "0" ]]; then
  run_or_preview "Prune dangling Docker volumes" docker volume prune -f
fi

section "FFE Runtime Artifacts"
for pair in \
  "$REPO_ROOT/logs logs" \
  "$DATA_DIR data" \
  "$REPO_ROOT/backups backups" \
  "$REPO_ROOT/build build"; do
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

section "FFE Decision / Data Retention"
DECISIONS_DIR="$DATA_DIR/decisions"
if [[ -d "$DECISIONS_DIR" ]]; then
  old_decisions=$(find "$DECISIONS_DIR" -name '*.json' -mtime +14 | wc -l | tr -d ' ')
  bak_files=$(find "$DECISIONS_DIR" -name '*.bak' | wc -l | tr -d ' ')
  log "Decision files older than 14 days: $old_decisions"
  log "Decision backup (.bak) files: $bak_files"
  if [[ "$old_decisions" != "0" ]]; then
    run_or_preview "Remove decision files older than 14 days" find "$DECISIONS_DIR" -name '*.json' -mtime +14 -delete
  fi
  if [[ "$bak_files" != "0" ]]; then
    run_or_preview "Remove decision backup (.bak) files" find "$DECISIONS_DIR" -name '*.bak' -delete
  fi
fi

section "Misc Data Retention"
for subdir in crash_dumps exports dlq training_logs; do
  target="$DATA_DIR/$subdir"
  if [[ -d "$target" ]]; then
    size=$(du -sh "$target" 2>/dev/null | awk '{print $1}')
    count=$(find "$target" -type f -mtime +30 | wc -l | tr -d ' ')
    log "$subdir: $size total, $count files older than 30 days"
    if [[ "$count" != "0" ]]; then
      run_or_preview "Remove $subdir files older than 30 days" find "$target" -type f -mtime +30 -delete
    fi
  fi
done

section "Scratch / Worktree Cleanup"
# These scratch/worktree globs are intentionally absolute host-level paths rather than repo-relative.
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
