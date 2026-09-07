# Lab 3 — `create_before_destroy`: proving the actual replacement order

**Goal:** Prove, with real evidence (not a guess), which order Terraform
actually performs a forced replacement in. By default: destroy the old
resource, then create the new one — meaning anything depending on that
resource (a load balancer target, a DNS record) sees a real gap with nothing
there. `create_before_destroy = true` flips it: create the new one first,
then destroy the old one, once the new one exists.

**Task:** Open `main.tf`. `null_resource.server`'s `triggers.version` will
change between applies, forcing a replacement. Add:
```hcl
lifecycle {
  create_before_destroy = true
}
```

**Verify:**
```bash
./verify.sh
```
Applies with `version_tag=v1`, then applies again with `version_tag=v2`
using `terraform apply -json` — the same machine-readable event stream tools
like Atlantis and CI pipelines actually consume. It parses the stream for
the sequence of `apply_start` events and checks whether `create` or `delete`
happened first. PASS requires `create` first.

**SOCH:**
- This lab verifies via Terraform's own `-json` event log instead of a
  provisioner writing to a file. During development of this exact lab, a
  `local-exec` provisioner with `when = destroy` was tried first — it never
  fired at all on the "deposed" object that `create_before_destroy` produces
  (a real, reproducible Terraform behavior, not a mistake in the command).
  What does that suggest about how much you should trust destroy-time
  provisioners for anything you actually depend on, versus checking the
  provider/resource's real state or Terraform's own structured output?
- `create_before_destroy` requires the resource to be creatable in duplicate
  for a moment (two resources with almost-identical config existing at
  once). What real AWS resource have you seen in `../01_terraform_iac.md`
  that this would actually FAIL for, because AWS itself won't allow two to
  exist with the same identifying attribute? *(hint: think about anything
  requiring a globally or regionally unique name)*
