#!/usr/bin/env bash
# Spec Kit structure check (see .specify/memory/constitution.md).
# - The constitution exists.
# - Every specs/NNN-*/ directory has non-empty spec.md, plan.md and tasks.md.
# - Every spec.md has a Workflows section.
# - A stateful spec (one with a state-machine heading or a stateDiagram) has a
#   transition table with the columns From | Event | Guard | To | Effect.
set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

fail=0
err() { echo "::error file=$1::$2"; fail=1; }

constitution=.specify/memory/constitution.md
if [[ ! -s "$constitution" ]]; then
  err "$constitution" "missing or empty constitution"
else
  echo "ok: $constitution"
fi

shopt -s nullglob
dirs=(specs/[0-9][0-9][0-9]-*/)
if (( ${#dirs[@]} == 0 )); then
  err specs "no specs/NNN-* directories found"
fi

table_re='^[[:space:]]*\|[[:space:]]*from[[:space:]]*\|[[:space:]]*event[[:space:]]*\|[[:space:]]*guard[[:space:]]*\|[[:space:]]*to[[:space:]]*\|[[:space:]]*effect[[:space:]]*\|'
stateful_re='^#+ .*(state machine|states|stateful|lifecycle)|stateDiagram'

for d in "${dirs[@]}"; do
  d=${d%/}
  for f in spec.md plan.md tasks.md; do
    if [[ -s "$d/$f" ]]; then echo "ok: $d/$f"; else err "$d/$f" "missing or empty (required by Spec Kit)"; fi
  done
  spec="$d/spec.md"
  [[ -s "$spec" ]] || continue
  if ! grep -Eiq '^#+ .*workflows' "$spec"; then
    err "$spec" "no Workflows section"
  fi
  if grep -Eiq "$stateful_re" "$spec"; then
    if grep -Eiq "$table_re" "$spec"; then
      echo "ok: $spec is stateful and has a transition table"
    else
      err "$spec" "stateful spec without a 'From | Event | Guard | To | Effect' transition table"
    fi
    if ! grep -q 'stateDiagram-v2' "$spec"; then
      echo "::warning file=$spec::stateful spec has no mermaid stateDiagram-v2"
    fi
  fi
done

exit "$fail"
