#!/usr/bin/env bash
# Agent Team Deploy Script
# Run this after creating agents to set up routing

set -e

echo "=== Agent Team Deploy ==="
echo ""

# List all agents
echo "[1/2] Configuring routing rules..."
echo ""

# Route Feishu user to pm-agent (uncomment to activate)
# openclaw agents bind pm-agent --bind "feishu:ou_4b78eb2dc6e5b8466080d416afedabb5"

echo "To route Arthur's Feishu messages to PM agent, run:"
echo "  openclaw agents bind pm-agent --bind \"feishu:ou_4b78eb2dc6e5b8466080d416afedabb5\""
echo ""
echo "To remove routing and keep default main agent:"
echo "  openclaw agents unbind pm-agent"
echo ""

# Verify agent configuration
echo "[2/2] Verifying agent status..."
openclaw agents list

echo ""
echo "=== Deploy Complete ==="
echo "Team agents ready. Use sessions_send to communicate between agents."
