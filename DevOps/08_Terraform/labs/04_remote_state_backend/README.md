# Lab 4 — S3 + DynamoDB remote state backend, made real

**Goal:** `../01_terraform_iac.md`'s "Backend — S3 + DynamoDB Lock" section
teaches the syntax. This lab makes it actually run — against **LocalStack**
(a local AWS-API-compatible emulator, no real cloud account or cost needed),
proving your state genuinely lands in "S3", not on local disk.

> **Setup (once):** `(cd ../_setup && docker compose up -d)` — starts
> LocalStack with S3 + DynamoDB. `verify.sh` checks it's reachable and fails
> fast with instructions if it isn't.

**Task:** Open `main.tf`. The `backend "s3"` block is configured for a real
bucket/table name and fake `test`/`test` credentials, but with **no
endpoint override** — meaning `terraform init` tries to reach real AWS and
fails on auth (there's no such account). Add:
```hcl
endpoints = {
  s3       = "http://localhost:4566"
  dynamodb = "http://localhost:4566"
}
use_path_style = true
```

**Verify:**
```bash
./verify.sh
```
Bootstraps the bucket + lock table directly in LocalStack via the AWS CLI
(the backend's own storage has to exist before Terraform can use it — same
"one-time bootstrap" idea as `../practical/01_terraform_lab.md` Lab 3), then
runs `terraform init` + `apply`. PASS requires: init actually succeeds
(proving it reached LocalStack, not real AWS), the state object is
verifiably sitting in the LocalStack S3 bucket via `aws s3 ls`, and there's
no local `terraform.tfstate` file at all.

**SOCH:**
- `terraform init`'s error message on the unfilled stub complains about a
  region/location mismatch against a REAL S3 bucket somewhere in `eu-west-2`
  that isn't yours — Terraform genuinely tried to reach actual AWS with the
  fake `test`/`test` credentials. What does that tell you about the blast
  radius of a backend misconfiguration, if those had been real credentials
  instead of fake ones?
- The Terraform CLI printed a deprecation warning for `dynamodb_table`,
  suggesting `use_lockfile` (native S3 locking, no DynamoDB table needed)
  instead. Given `../01_terraform_iac.md` teaches the DynamoDB pattern
  because it's still what most existing production codebases use, when
  would adopting the newer `use_lockfile` approach actually be worth a
  migration, versus leaving a working DynamoDB-locked backend alone?
