#!/bin/sh
# Opens a Forgejo issue when a workflow fails.
#
# The scheduled jobs here fail silently: sync-github-prs ran on a dead
# GH_MIRROR_TOKEN twice a day for five days, twelve failed runs, and nothing
# said so. Forgejo does not notify on scheduled-run failures, and nobody reads
# the Actions tab unprompted. An open issue is somewhere a human already looks.
#
# Uses FJ_API_TOKEN, which the repo already has and already grants issue write.
set -eu

: "${FORGEJO_API:?}" "${FORGEJO_REPO:?}" "${FORGEJO_TOKEN:?}" "${WORKFLOW:?}" "${RUN_URL:?}"

TITLE="CI failure: $WORKFLOW"

# ponytail: one open issue per workflow, not one per failed run. Twice-daily
# failures would otherwise file twelve issues in five days. The open issue is
# the signal. Close it when fixed; the next failure opens a fresh one. If you
# ever want per-run detail, POST a comment here instead of exiting early.
OPEN=$(curl -sSf -H "Authorization: token $FORGEJO_TOKEN" \
  "$FORGEJO_API/repos/$FORGEJO_REPO/issues?state=open&type=issues" \
  | jq --arg t "$TITLE" '[.[] | select(.title == $t)] | length')

if [ "$OPEN" -gt 0 ]; then
  echo "issue already open for $WORKFLOW, not filing another"
  exit 0
fi

BODY="\`$WORKFLOW\` failed.

Run: $RUN_URL

Filed automatically by .forgejo/notify-failure.sh. One issue per workflow, not
per run, so this stays open and quiet while the job keeps failing. Close it
once fixed and the next failure opens a new one."

curl -sSf -X POST \
  -H "Authorization: token $FORGEJO_TOKEN" \
  -H "Content-Type: application/json" \
  "$FORGEJO_API/repos/$FORGEJO_REPO/issues" \
  -d "$(jq -n --arg t "$TITLE" --arg b "$BODY" '{title:$t, body:$b}')" > /dev/null

echo "opened issue: $TITLE"
