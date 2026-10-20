#!/usr/bin/env bash
# Runs all three real-model evaluation arms for one teammate's slice of the scenarios.
#
#   scripts/team_eval.sh 1            # slice 1 = S01-S08, 2 = S09-S15, 3 = S16-S22
#   scripts/team_eval.sh 2 S11,S14    # rerun only some scenarios of slice 2 (after a quota reset)
#
# Arms (same model, same machine, so arms 2 and 3 replay the unchanged research steps from
# this machine's model-response cache and only pay for the calls that differ):
#   real_v1_part<N>     assessor prompt v1, modifier step on    (L2 baseline)
#   real_v2_part<N>     assessor prompt v2, modifier step on    (L2 variant, L3 "before")
#   real_nomod_part<N>  assessor prompt v2, modifier step off   (L3 "after")
# Requires the stack running with your own key in .env (see docs/team_eval.md).
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
  1) ids="S01,S02,S03,S04,S05,S06,S07,S08" ;;
  2) ids="S09,S10,S11,S12,S13,S14,S15" ;;
  3) ids="S16,S17,S18,S19,S20,S21,S22" ;;
  *) echo "usage: $0 <1|2|3> [comma-separated scenario ids]" >&2; exit 2 ;;
esac
slice="$1"
ids="${2:-$ids}"
suffix=""
[ -n "${2:-}" ] && suffix="_rerun$(date +%H%M)"

agents() {  # restart the agents and API with the modifier step on or off, wait until healthy
  MODIFIER_SEARCH_ENABLED="$1" docker compose up -d --no-deps --wait researcher assessor api >/dev/null 2>&1 \
    || { echo "could not restart the agents - is the stack up? (docker compose up -d)" >&2; exit 1; }
}
arm() {     # arm <label> <variant>
  echo "== $1 ($2) on $ids"
  docker compose --profile tools run --rm --no-deps eval python -m bpc.evaluation.run_eval \
    --variant "$2" --label "$1_part${slice}${suffix}" --only "$ids" --reuse-model-cache --timeout 900 \
    --out "${EVAL_OUT:-eval/results}" | { grep -E '^\{|^provider degraded' || true; }
}

agents true
arm real_v1 v1
arm real_v2 v2
agents false
arm real_nomod v2
agents true    # leave the stack in its default configuration

echo
echo "Done. Commit eval/results/real_*_part${slice}${suffix}.* and push."
echo "If a line above says 'provider degraded', rerun those ids after the quota resets:"
echo "  scripts/team_eval.sh ${slice} <ids>"
