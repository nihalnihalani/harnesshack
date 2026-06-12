#!/usr/bin/env bash
# Show-and-tell for the Guild sponsor rep.
# Demonstrates exactly where IncidentSherpa gets stuck creating a per-incident
# audit/governance session via the REST API. Token is read from `guild auth
# token` and never printed. Run:  bash scripts/guild_repro.sh
set -u

TOKEN=$(guild auth token 2>/dev/null)
WS="019ebd7d-a793-3bb9-0000-a78c98697748"   # workspace 0612hack
API="https://app.guild.ai/api"

echo "We want: one Guild session per incident, then append our own typed audit"
echo "events to it (tamper-proof trail). Here is where we get stuck:"
echo
echo "\$ POST $API/workspaces/<ws>/sessions   (auth: Bearer <our PAT>)"
echo "  body: {\"name\":\"incident-123\"}"
curl -s -m 15 -X POST "$API/workspaces/$WS/sessions" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"incident-123"}'
echo; echo

echo "  body: {\"name\":\"incident-123\",\"session_type\":\"agent_test\"}"
curl -s -m 15 -X POST "$API/workspaces/$WS/sessions" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"incident-123","session_type":"agent_test"}'
echo; echo

echo "QUESTION: a session needs session_type chat (needs a prompt) or agent_test"
echo "(needs an agent_version_id). What is the intended way to use a Guild session"
echo "as a per-incident audit/governance container for OUR agent's events? Do we"
echo "register IncidentAgent as a Guild agent first to get an agent_version_id?"
