#!/usr/bin/env bash
# Self-checking verifier for Lab 1 -- state surgery via `moved` blocks.
# PASS only if the resource's random hex value survives the rename UNCHANGED,
# proving Terraform updated its state in place instead of destroy+recreate.
set -uo pipefail
cd "$(dirname "$0")"
SCRATCH=$(mktemp -d)
FAIL=0

cleanup() {
  rm -rf "$SCRATCH"
}
trap cleanup EXIT

echo "==> [setup] applying _before/main.tf in a scratch dir (simulates already-deployed infra)"
cp _before/main.tf "$SCRATCH/main.tf"
(cd "$SCRATCH" && terraform init -input=false >/dev/null 2>&1 && terraform apply -auto-approve -input=false >/dev/null 2>&1)
before_hex=$(cd "$SCRATCH" && terraform output -raw server_a_hex 2>/dev/null)

if [ -z "$before_hex" ]; then
  echo "FAIL: could not even set up the 'before' state -- check terraform is installed and the random provider downloads correctly"
  exit 1
fi
echo "    OK -- random_id.server_a.hex = $before_hex (this must NOT change below)"

echo "==> [your work] replacing main.tf with the renamed version, applying again in the SAME state"
cp main.tf "$SCRATCH/main.tf"

plan_summary=$(cd "$SCRATCH" && terraform plan -input=false -no-color 2>&1 | grep -E "Plan:" || true)
echo "    plan says: ${plan_summary:-'(no Plan: line found)'}"

(cd "$SCRATCH" && terraform apply -auto-approve -input=false >/dev/null 2>&1)
after_hex=$(cd "$SCRATCH" && terraform output -raw web_a_hex 2>/dev/null)

if [ -z "$after_hex" ]; then
  echo "FAIL: after applying main.tf, 'web_a_hex' output is empty -- check main.tf's output block"
  exit 1
fi

if [ "$before_hex" = "$after_hex" ]; then
  echo "    OK -- random_id.web_a.hex = $after_hex, IDENTICAL to before ($before_hex)"
  echo "    The moved block worked: Terraform renamed the address in state, no destroy/recreate."
else
  echo "FAIL: hex changed from $before_hex to $after_hex -- Terraform destroyed the old resource"
  echo "      and created a brand-new one instead of moving it. Most likely cause: the 'moved'"
  echo "      block TODO was never added to main.tf."
  FAIL=1
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- same underlying resource survived a rename with zero destroy/recreate."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
