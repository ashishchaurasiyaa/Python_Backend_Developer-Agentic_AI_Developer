# Lab 5 — `terraform import`: adopting existing infra without data loss

**Goal:** The single most common way real infrastructure meets Terraform for
the first time: it already exists — someone click-ops'd or CLI'd it into
being months ago — and it needs to come under Terraform management
**without being destroyed and recreated** (which, for an S3 bucket with
real objects inside, means real data loss).

> **Setup (once):** `(cd ../_setup && docker compose up -d)` if not already
> running from Lab 4.

**Task:** `verify.sh` creates a bucket named `tf-lab-imported-bucket`
**outside Terraform** (plain AWS CLI against LocalStack), with a
`marker.txt` object inside it, before you run anything. Open `main.tf` —
it declares a matching `aws_s3_bucket.adopted` resource but has no idea the
real bucket already exists. Add an `import` block:
```hcl
import {
  to = aws_s3_bucket.adopted
  id = "tf-lab-imported-bucket"
}
```

**Verify:**
```bash
./verify.sh
```
Without the import block, `terraform apply` tries to CREATE the bucket and
fails fast with `BucketAlreadyExists` — real, informative evidence that
blindly declaring a resource doesn't "notice" pre-existing infra on its
own. With the import block, PASS requires: the apply plan says
`1 to import` (not `1 to add`), `aws_s3_bucket.adopted` shows up in
`terraform state list`, `marker.txt` is **still there** afterward (proving
nothing was destroyed), and a follow-up `terraform plan` reports
`No changes` (proving your config's attributes match reality exactly).

**SOCH:**
- The unfilled stub fails with `BucketAlreadyExists` — a real, correct error
  telling you exactly what went wrong. What would have happened instead if
  the resource type had been something Terraform is willing to silently
  overwrite or reset (imagine an IAM policy attachment) instead of one that
  errors loudly on conflict?
- `terraform plan` reporting `No changes` after the import proves your
  `bucket = "tf-lab-imported-bucket"` argument was a complete, exact match.
  If the real bucket had versioning enabled (set outside Terraform) and your
  `aws_s3_bucket` resource block said nothing about versioning, would
  `terraform plan` still show `No changes`, or would it show a "drift"? What
  does that imply about how thoroughly you need to write a resource block
  before importing into it, versus after?
