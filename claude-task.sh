#!/usr/bin/env bash
# ============================================================
# claude-task — Claude Code task runner for OpenClaw agents
# Usage: claude-task "task description" [--allow-write]
# ============================================================
set -euo pipefail

PROMPT="${1:?Usage: claude-task <prompt> [--allow-write]}"
ALLOW_WRITE="${2:-}"

ARGS=(-p "$PROMPT" --print)

if [ "$ALLOW_WRITE" = "--allow-write" ]; then
    ARGS+=(--allow-dangerously-skip-permissions)
fi

cd /home/pz04-a-001/.openclaw/workspace/AnyDocConverter

# Run claude with timeout (5 min max per task)
timeout 300 claude "${ARGS[@]}" 2>&1
