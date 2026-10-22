#!/bin/bash
# usage: ghrun.sh <workflow file|id> [json inputs]  -> dispatch (if inputs given), wait for latest run, print annotations
WF=$1; IN=$2; R=jobimtg/finance-video-insights; API=https://api.github.com/repos/$R
c(){ env -u GH_TOKEN curl -sS -H "Accept: application/vnd.github+json" "$@"; }
if [ -n "$IN" ]; then
  B=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  c -X POST -H "Content-Type: application/json" $API/actions/workflows/$WF/dispatches -d "{\"ref\":\"main\",\"inputs\":$IN}"
  for i in $(seq 1 30); do sleep 4; ID=$(c "$API/actions/workflows/$WF/runs?per_page=1&created=>=$B" | python3 -c "import json,sys;r=json.load(sys.stdin)['workflow_runs'];print(r[0]['id'] if r else '')"); [ -n "$ID" ] && break; done
else
  ID=$(c "$API/actions/workflows/$WF/runs?per_page=1" | python3 -c "import json,sys;print(json.load(sys.stdin)['workflow_runs'][0]['id'])")
fi
echo run $ID
for i in $(seq 1 150); do S=$(c $API/actions/runs/$ID | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['status'],d['conclusion'])"); case "$S" in completed*) break;; esac; sleep 8; done
echo $S
for J in $(c $API/actions/runs/$ID/jobs | python3 -c "import json,sys;[print(j['id']) for j in json.load(sys.stdin)['jobs']]"); do
 c "$API/check-runs/$J/annotations?per_page=100" | python3 -c "
import json,sys
for a in json.load(sys.stdin): print('['+a['annotation_level']+']',a['title'],'\n',a['message'])"
done
