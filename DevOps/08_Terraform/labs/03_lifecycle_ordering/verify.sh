#!/usr/bin/env bash
# Self-checking verifier for Lab 3 -- create_before_destroy ordering.
# PASS only if `terraform apply -json`'s own event stream shows the CREATE
# action starting before the DELETE action, on a forced replacement.
set -uo pipefail
cd "$(dirname "$0")"
SCRATCH=$(mktemp -d)
FAIL=0

cleanup() {
  rm -rf "$SCRATCH"
}
trap cleanup EXIT

cp main.tf "$SCRATCH/main.tf"
cd "$SCRATCH"

echo "==> init + apply version_tag=v1"
terraform init -input=false >/dev/null 2>&1
terraform apply -auto-approve -input=false -var="version_tag=v1" >/dev/null 2>&1

echo "==> apply version_tag=v2 (forces replacement -- triggers changed), reading the -json event stream"
sequence=$(terraform apply -auto-approve -input=false -var="version_tag=v2" -json 2>&1 | python3 -c "
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        continue
    if d.get('type') == 'apply_start':
        hook = d.get('hook', {})
        print(hook.get('action'))
")

echo "    action order seen: $(echo "$sequence" | tr '\n' ' ')"

first_action=$(echo "$sequence" | head -1)

if [ "$first_action" = "create" ]; then
  echo "    OK -- 'create' was the FIRST action Terraform took on the replacement"
elif [ "$first_action" = "delete" ]; then
  echo "FAIL: 'delete' happened before 'create' -- that's Terraform's DEFAULT ordering."
  echo "      The TODO (lifecycle { create_before_destroy = true }) was never added."
  FAIL=1
else
  echo "FAIL: could not parse any apply_start actions from the -json output at all -- check terraform apply ran cleanly"
  FAIL=1
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- replacement happened new-before-old, exactly what create_before_destroy promises."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
