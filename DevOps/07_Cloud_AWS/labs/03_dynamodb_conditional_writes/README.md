# Lab 3 — DynamoDB conditional writes prevent lost updates

**Goal:** Prove, live, the classic **lost update** race: two writers (A, B)
both read `balance=100, version=1` into their own variables. A computes
`100+50=150` and writes it. B, using its own now-stale read of 100,
computes `100+30=130` and writes it — silently overwriting A's change.
Final balance: 130, not 180. **Nothing errors.** That silence is exactly
what makes lost updates dangerous — no exception, no log line, just quietly
wrong data.

**Task:** Open `lab.py`. `apply_delta()` does a plain, unconditional
`update_item` — whoever writes last wins, no matter how stale their read
was. Add a `ConditionExpression` checking the version hasn't moved, plus a
version increment on every successful write:
```python
table.update_item(
    Key={"account_id": account_id},
    UpdateExpression="SET balance = :new_balance, version = version + :one",
    ConditionExpression="version = :expected_version",
    ExpressionAttributeValues={
        ":new_balance": new_balance, ":one": 1, ":expected_version": expected_version,
    },
)
```

**Verify:**
```bash
./verify.sh
```
Runs `lab.py`'s A-then-B scenario, then **independently** reads the final
balance via the AWS CLI. PASS requires balance=150 (A's write preserved) —
not 130 (the lost update) — AND that B's write actually raised
`ConditionalCheckFailedException` in the process (not just a coincidentally
correct number).

**SOCH:**
- The unfilled stub uses DynamoDB's own atomic `SET balance = balance +
  :delta` accidentally would NOT have this bug at all (an earlier version
  of this exact lab used that expression and the race genuinely didn't
  reproduce — that's why `apply_delta()` here takes an already-computed
  `new_balance` instead). Why does computing the new value in *application
  code* create a race that DynamoDB's own atomic increment doesn't have?
- The fix here makes B's write **fail loudly** — it doesn't automatically
  retry B with a fresh read. Why is "fail and let the caller decide what to
  do next" the right boundary for the database layer, instead of the
  database silently retrying the write for you?
