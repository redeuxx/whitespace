#!/bin/sh
# Posts to a chat webhook when a workflow fails.
#
# The scheduled jobs here fail silently: sync-github-prs ran on a dead
# GH_MIRROR_TOKEN twice a day for five days, twelve failed runs, and nothing
# said so. Forgejo does not notify on scheduled-run failures and nobody reads
# the Actions tab unprompted.
#
# Filing a Forgejo issue was tried first and does not work: an issue authored
# by the repo owner's own token notifies nobody, so it is visible but silent,
# which is the bug rather than the fix.
set -eu

: "${NOTIFY_WEBHOOK:?}" "${WORKFLOW:?}" "${RUN_URL:?}" "${REPO:?}"

TEXT="CI failure: $REPO / $WORKFLOW
$RUN_URL"

# Discord wants {content}, Slack wants {text}. Mattermost, Rocket.Chat and
# Google Chat also take {text}, so that is the default.
case "$NOTIFY_WEBHOOK" in
  *discord.com*|*discordapp.com*) PAYLOAD=$(jq -n --arg c "$TEXT" '{content:$c}') ;;
  *)                              PAYLOAD=$(jq -n --arg c "$TEXT" '{text:$c}') ;;
esac

# ponytail: no dedupe. In chat, one message per failed run is the point; a job
# failing twice a day should say so twice a day. Add throttling only if it
# actually gets noisy.

# Loud on failure. A reporter that fails quietly is the bug being fixed.
if ! curl -sSf -X POST -H "Content-Type: application/json" \
       -d "$PAYLOAD" "$NOTIFY_WEBHOOK" > /dev/null; then
  echo "notify-failure: webhook POST failed" >&2
  exit 1
fi

echo "notified: $WORKFLOW"
