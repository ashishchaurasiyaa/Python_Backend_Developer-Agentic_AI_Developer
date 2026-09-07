#!/usr/bin/env bash
# Self-checking verifier for Lab 2 -- count's index-shift trap vs for_each's
# stable keys. PASS only if foreach_based["c"] survives removing "b" from the
# middle of the list with an UNCHANGED hex, while also proving (for contrast,
# not as a failure) that count_based["c"] does NOT survive unchanged.
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

echo "==> init + apply with names = [\"a\", \"b\", \"c\"]"
terraform init -input=false >/dev/null 2>&1
terraform apply -auto-approve -input=false >/dev/null 2>&1

count_before=$(terraform output -json count_based_hex 2>/dev/null)
foreach_before=$(terraform output -json foreach_based_hex 2>/dev/null)
echo "    count_based   before: $count_before"
echo "    foreach_based before: $foreach_before"

c_c_before=$(echo "$count_before" | python3 -c "import json,sys; print(json.load(sys.stdin).get('c',''))" 2>/dev/null)
fe_c_before=$(echo "$foreach_before" | python3 -c "import json,sys; print(json.load(sys.stdin).get('c',''))" 2>/dev/null)
fe_a_before=$(echo "$foreach_before" | python3 -c "import json,sys; print(json.load(sys.stdin).get('a',''))" 2>/dev/null)

if [ -z "$c_c_before" ] || [ -z "$fe_c_before" ]; then
  echo "FAIL: could not read hex values for key 'c' from one of the outputs -- check the output block syntax"
  exit 1
fi

echo
echo "==> removing 'b' from the middle: applying with names = [\"a\", \"c\"]"
terraform apply -auto-approve -input=false -var='names=["a","c"]' >/dev/null 2>&1

count_after=$(terraform output -json count_based_hex 2>/dev/null)
foreach_after=$(terraform output -json foreach_based_hex 2>/dev/null)
echo "    count_based   after: $count_after"
echo "    foreach_based after: $foreach_after"

c_c_after=$(echo "$count_after" | python3 -c "import json,sys; print(json.load(sys.stdin).get('c',''))" 2>/dev/null)
fe_c_after=$(echo "$foreach_after" | python3 -c "import json,sys; print(json.load(sys.stdin).get('c',''))" 2>/dev/null)
fe_a_after=$(echo "$foreach_after" | python3 -c "import json,sys; print(json.load(sys.stdin).get('a',''))" 2>/dev/null)
fe_b_after=$(echo "$foreach_after" | python3 -c "import json,sys; print(json.load(sys.stdin).get('b','MISSING'))" 2>/dev/null)

echo
if [ "$c_c_before" != "$c_c_after" ]; then
  echo "    EXPECTED BUG confirmed -- count_based's 'c' hex changed ($c_c_before -> $c_c_after)"
  echo "    even though 'c' was never removed. count identifies by POSITION, and 'c' shifted"
  echo "    from index 2 to index 1 when 'b' was removed."
else
  echo "    NOTE: count_based's 'c' hex did not change ($c_c_before) -- unexpected, but not what we're grading"
fi

if [ "$fe_b_after" = "MISSING" ]; then
  echo "    OK -- foreach_based no longer has a 'b' entry (it was actually removed, as intended)"
else
  echo "FAIL: foreach_based still has a 'b' entry after removing it from var.names -- TODO not done (still count-based)"
  FAIL=1
fi

if [ -n "$fe_a_before" ] && [ "$fe_a_before" = "$fe_a_after" ]; then
  echo "    OK -- foreach_based['a'] unchanged ($fe_a_after)"
else
  echo "FAIL: foreach_based['a'] changed ($fe_a_before -> $fe_a_after) -- shouldn't have, 'a' was never touched"
  FAIL=1
fi

if [ -n "$fe_c_before" ] && [ "$fe_c_before" = "$fe_c_after" ]; then
  echo "    OK -- foreach_based['c'] UNCHANGED ($fe_c_after) despite 'b' being removed from the middle"
else
  echo "FAIL: foreach_based['c'] changed ($fe_c_before -> $fe_c_after)."
  echo "      Most likely cause: the resource block is still using 'count' (TODO not done) --"
  echo "      it has the exact same index-shift bug as count_based above."
  FAIL=1
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- for_each kept 'a' and 'c' completely untouched; only 'b' was removed."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
