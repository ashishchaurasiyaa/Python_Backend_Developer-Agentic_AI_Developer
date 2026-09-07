# Lab 1 — State surgery via `moved` blocks

**Goal:** Prove, live, that Terraform tracks resources by **address**
(resource type + name in your `.tf` files) — not by what the resource
actually is. Rename a resource block with no other changes, and Terraform's
default move is destroy the old one, create a new one. For a `random_id`
that's harmless; for a real S3 bucket or database, that's data loss.

**Task:** `_before/main.tf` (already applied by `verify.sh` — don't edit it)
represents infra someone deployed weeks ago, named `random_id.server_a`.
`main.tf` renames it to `random_id.web_a` — a reasonable rename — but
without telling Terraform they're the same resource. Add a `moved` block:
```hcl
moved {
  from = random_id.server_a
  to   = random_id.web_a
}
```

**Verify:**
```bash
./verify.sh
```
Applies `_before/main.tf` in a scratch directory, captures the resulting
random hex value, then swaps in your `main.tf` (same state) and applies
again. PASS only if the hex value is **identical** before and after — proving
Terraform moved the address in state instead of destroying and recreating.
It also prints the `terraform plan` summary line so you can see `1 to add, 1
to destroy` when the TODO isn't done, versus `0 to add, 0 to destroy` when it is.

**SOCH:**
- `moved` blocks are Terraform's newer, declarative alternative to running
  `terraform state mv` by hand on the CLI. What's the advantage of the
  `moved` block living in the `.tf` file itself, checked into git, over a
  one-off CLI command someone ran once and never wrote down?
- If this had been a real `aws_db_instance`, what would "destroy the old one,
  create a new one" have actually cost you, beyond just downtime?
