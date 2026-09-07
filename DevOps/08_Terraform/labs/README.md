# Terraform Labs — Runnable Exercises

`../practical/01_terraform_lab.md` already has 4 solid walkthroughs (first
S3 bucket, variables/workspaces, modules + remote backend, state drift) —
but every solution ships inline in the same file, against a real AWS
account. This folder is for *doing*, and deliberately needs **no AWS
account and no cost**: 3 labs run fully offline against `random`/`null`
providers, and 2 run against **LocalStack** (a local, free, AWS-API-
compatible emulator) for the parts that genuinely need something S3-shaped
to talk to. Every lab has a TODO-stub `main.tf` and a `verify.sh` that
checks real Terraform/AWS-API state and tells you PASS or FAIL.

## Setup

Labs 1-3 need only Terraform itself:
```bash
brew install hashicorp/tap/terraform
```

Labs 4-5 also need LocalStack (via Docker):
```bash
cd DevOps/08_Terraform/labs
(cd _setup && docker compose up -d)     # starts LocalStack (S3 + DynamoDB), ~10s
```

Each lab's `verify.sh` runs `terraform init`/`apply` in its own scratch
directory (never in the lab folder itself) and cleans up after itself, so
labs can be run in any order with no leftover state.

## Labs

| # | Lab | What it proves | Needs LocalStack? |
|---|---|---|---|
| 1 | [01_state_surgery](01_state_surgery) | A `moved` block lets you rename a resource address without Terraform destroying and recreating it | No |
| 2 | [02_count_vs_foreach](02_count_vs_foreach) | `count`'s index-shift trap: removing a middle list item reshuffles everything after it; `for_each`'s stable keys don't | No |
| 3 | [03_lifecycle_ordering](03_lifecycle_ordering) | `create_before_destroy` actually flips replacement order — proven via `terraform apply -json`'s own event stream | No |
| 4 | [04_remote_state_backend](04_remote_state_backend) | The S3+DynamoDB backend from `../01_terraform_iac.md`, made real — state genuinely lands in an S3-compatible bucket, not on local disk | Yes |
| 5 | [05_import_existing](05_import_existing) | `terraform import` adopts already-existing infra into state without destroying and recreating it | Yes |

## Protocol

```
1. Open the lab's main.tf, read the comment block at the top
2. Fill in the TODO(s)
3. Run ./verify.sh -> PASS moves you to the next lab; FAIL tells you
   specifically what it expected vs what it saw
4. Answer the README's SOCH questions out loud before moving on
```

## Checklist

- [ ] Lab 1 — State surgery via `moved` blocks
- [ ] Lab 2 — `count` vs `for_each`
- [ ] Lab 3 — `create_before_destroy` ordering
- [ ] Lab 4 — S3 + DynamoDB remote state backend (LocalStack)
- [ ] Lab 5 — `terraform import` (LocalStack)
