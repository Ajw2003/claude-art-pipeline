#!/bin/sh
# overnight.sh - start Claude Code for an unattended run that never waits on a person.
#
#   sh overnight.sh                      interactive session
#   sh overnight.sh -p "make the hero"   headless, any other `claude` arguments pass through
#
# art-pipeline: ART_PIPELINE=unattended - art needs no human-approved spec and AskUserQuestion is
#   refused. Still enforced: approvals/config/ledger cannot be edited, models and animation still
#   need their review sheets, forged approvals still block the stop.
# house-rules: every feature group off except autosave and handoff (they keep work saved overnight).
#   The destructive-command guard, the main-branch guard and the credit check have no switch and stay.
#   A prompt those guards still raise is refused after 30 seconds and listed under "Waiting on you".
set -eu

export ART_PIPELINE=unattended

for v in HOUSE_RULES_LOOP HOUSE_RULES_ISSUES HOUSE_RULES_PAGES HOUSE_RULES_DELEGATION HOUSE_RULES_AGENTS \
         HOUSE_RULES_CLEAR_WRITING HOUSE_RULES_PLAIN_SUMMARY HOUSE_RULES_VISUAL_CHECK HOUSE_RULES_PARITY \
         HOUSE_RULES_VOICE HOUSE_RULES_HARVEST HOUSE_RULES_COMMIT_CHECK HOUSE_RULES_HANDOVER \
         HOUSE_RULES_RERUNS HOUSE_RULES_DISKREPORT; do
  export "$v=off"
done
export HOUSE_RULES_PROMPT_TIMEOUT=30

exec claude --dangerously-skip-permissions "$@"
