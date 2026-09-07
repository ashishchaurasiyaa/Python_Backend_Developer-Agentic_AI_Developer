# Lab 2 — `count`'s index-shift trap vs `for_each`'s stable keys

**Goal:** Prove, live, the single most-cited reason senior Terraform users
default to `for_each` over `count` for anything list-like: `count` identifies
resources by **position** (index 0, 1, 2...). Remove an item from the
**middle** of the list and everything after it shifts down one slot —
Terraform doesn't see "one thing removed", it sees "the thing at index 1
changed" and reshuffles resources that were never conceptually touched.
`for_each` identifies resources by a **stable key**, so removing one item
touches only that one.

**Task:** Open `main.tf`. `count_based` is a fixed contrast case — don't
touch it. `foreach_based` is currently an identical copy with the same bug.
Convert it: change `count = length(var.names)` to
`for_each = toset(var.names)`, change the keeper from
`var.names[count.index]` to `each.value`, and update its output block's
for-expression to key by `k` instead of `var.names[i]`.

**Verify:**
```bash
./verify.sh
```
Applies with `names = ["a", "b", "c"]`, captures each resource's hex value,
then applies again with `"b"` removed from the middle
(`names = ["a", "c"]`). It shows — as expected evidence, not a failure —
that `count_based["c"]`'s hex changes even though "c" was never removed.
Then it checks `foreach_based`: PASS requires `"b"` is gone, and `"a"`/`"c"`
keep the **exact same** hex values as before.

**SOCH:**
- `count_based["c"]`'s hex changing is not a Terraform bug — it's doing
  exactly what its state model promises (position-based identity). Given
  that, why is `count` still a reasonable choice for something like "spin up
  N identical worker nodes, doesn't matter which is which"?
- If `var.names` had instead been `["a", "b", "c"]` → `["a", "b"]` (removing
  from the **end**, not the middle), would `count_based` have shown the same
  bug? Why does removal position matter for `count` but not for `for_each`?
