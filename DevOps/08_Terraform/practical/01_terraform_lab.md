# Terraform — Hands-On Lab
**DevOps Track · Phase 8 Practical**

## Prerequisites

- Terraform CLI installed (`brew install terraform` or download from hashicorp.com) — verify with `terraform version`, this track assumes >= 1.7.0
- An AWS account with programmatic access (`aws configure` with an access key), **or** [LocalStack](https://localstack.cloud/) running locally if you want zero AWS cost/risk while learning — `docker run -d -p 4566:4566 localstack/localstack`, then point the provider at `endpoints { s3 = "http://localhost:4566" ... }`
- If using real AWS: everything in this lab fits comfortably in the free tier (S3, an occasional t3.micro EC2). Still run `terraform destroy` after each lab — don't leave resources running overnight by accident.
- A text editor and basic familiarity with the concepts in `../01_terraform_iac.md` — read that file first if you haven't; this lab assumes you know what a provider/resource/state/module is

Work in a fresh directory per lab (`mkdir lab1 && cd lab1`) so state files don't collide.

---

## Lab 1: First Terraform Config — Provision an S3 Bucket

**Objective:** Get from zero to a real, applied, and destroyed AWS resource, and understand what `init`/`plan`/`apply`/`destroy` each actually do.

**Task:**
1. Create a directory `lab1-s3/` with `main.tf`.
2. Configure the `aws` provider, pinned to `~> 5.0`, region `ap-south-1` (or your preferred region).
3. Declare a variable `bucket_name` (string, no default — you'll supply it).
4. Declare a resource `aws_s3_bucket` named `this` using `var.bucket_name`. Bucket names are globally unique across ALL of AWS — use something like `<yourname>-tf-lab1-<random-number>`.
5. Add an `aws_s3_bucket_versioning` resource enabling versioning on that bucket.
6. Add an `aws_s3_bucket_public_access_block` resource blocking all four public-access settings.
7. Add an output `bucket_arn` exposing the bucket's ARN.
8. Run `terraform init`, then `terraform validate`, then `terraform plan -var="bucket_name=..."`, read the plan output line by line, then `terraform apply` (same var).
9. Confirm the bucket exists (`aws s3 ls | grep <name>` or check the console).
10. Run `terraform destroy` to tear it down.

<details>
<summary>Solution / walkthrough</summary>

```hcl
# main.tf
terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-south-1"
}

variable "bucket_name" {
  description = "Globally unique S3 bucket name"
  type        = string
}

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "bucket_arn" {
  value = aws_s3_bucket.this.arn
}
```

```bash
terraform init                                     # downloads the aws provider plugin
terraform validate                                 # catches syntax errors before you burn a plan cycle
terraform plan -var="bucket_name=ashish-tf-lab1-8823"
terraform apply -var="bucket_name=ashish-tf-lab1-8823"
terraform destroy -var="bucket_name=ashish-tf-lab1-8823"
```

**Why each command matters:** `init` downloads provider plugins and sets up the backend — you re-run it whenever you add a new provider/module. `validate` is a free syntax/internal-consistency check that catches typos before Terraform even talks to AWS. `plan` is a dry run — it tells you exactly what would change without touching anything; reading it is non-negotiable habit-building, not busywork. `apply` re-runs the plan and asks for a literal "yes" before executing. `destroy` is the mirror image of apply — it computes what needs deleting and asks for confirmation too.
</details>

---

## Lab 2: Variables, Validation, Outputs, and Workspaces

**Objective:** Practice validated inputs and the dev/staging/prod workspace pattern from the same configuration.

**Task:**
1. Extend Lab 1 into a new directory `lab2-workspaces/`.
2. Add a variable `environment` (string) with a `validation` block restricting it to `["dev", "staging", "prod"]`.
3. Make the bucket name computed from environment: `bucket_name = "<yourname>-tf-lab2-${var.environment}"`.
4. Add a variable `lifecycle_expiration_days` (number, default `90`) and an `aws_s3_bucket_lifecycle_configuration` resource that expires objects after that many days.
5. Create `terraform.tfvars` with a default `environment = "dev"`.
6. Create two workspaces, `dev` and `staging`, and `apply` in each — confirm two separate buckets exist and `terraform workspace list` shows both.
7. Deliberately pass `environment = "prodd"` (typo) and confirm the validation block rejects it at plan time, before touching AWS.
8. Print `terraform.workspace` as an output and confirm it changes per workspace.

<details>
<summary>Solution / walkthrough</summary>

```hcl
variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "lifecycle_expiration_days" {
  type    = number
  default = 90
}

resource "aws_s3_bucket" "this" {
  bucket = "ashish-tf-lab2-${var.environment}"
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    id     = "expire-old-objects"
    status = "Enabled"
    expiration {
      days = var.lifecycle_expiration_days
    }
  }
}

output "current_workspace" {
  value = terraform.workspace
}
```

```bash
terraform workspace new dev
terraform workspace new staging
terraform workspace select dev
terraform apply -var="environment=dev"

terraform workspace select staging
terraform apply -var="environment=staging"

terraform workspace list          # * marks the currently selected one
terraform workspace select dev
terraform plan -var="environment=prodd"   # rejected at plan time — the validation block, not AWS, caught it
```

Expected validation failure:
```
Error: Invalid value for variable
  environment must be one of: dev, staging, prod.
```

Each workspace has its own state file under the same backend — `dev` and `staging` are structurally identical configs with different variable values, exactly the pattern from the lesson file. Clean up both: `terraform destroy` in each workspace before deleting them (`terraform workspace select default && terraform workspace delete dev`).
</details>

---

## Lab 3: Refactor Into a Reusable Module + Remote State Backend

**Objective:** Move from a single flat config to a production-shaped layout: a reusable `s3-bucket` module consumed twice, backed by an S3 + DynamoDB remote state backend — the same shape described in the lesson file's "Modules" and "Backend" sections.

**Task:**
1. Bootstrap the backend infrastructure by hand (a one-time chicken-and-egg step, done outside the module you're about to write): create an S3 bucket for state and a DynamoDB table for locking.
2. Create `modules/s3-bucket/` with `variables.tf`, `main.tf`, `outputs.tf` — accepting `bucket_name`, `versioning_enabled` (default `true`), `lifecycle_expiration_days` (default `365`), and `tags` (default `{}`); the module itself creates the bucket, versioning, lifecycle rule, and a public-access block (baked-in security default, not opt-in).
3. In a root config, add an S3 backend block pointing at the bucket/table you bootstrapped, with a unique `key`.
4. Call the module twice: once for an "uploads" bucket (90-day expiration) and once for an "audit-logs" bucket (2555-day / ~7-year expiration), with different `tags`.
5. Output both buckets' ARNs from the root config.
6. Apply, confirm both buckets exist with the right lifecycle settings, then open the state file's `key` in the S3 console and confirm it's really there (not on local disk).
7. Simulate a second engineer: open a second terminal, `cd` into the same directory, and run `terraform apply` at the same moment as the first terminal. Observe the lock behavior (the second one should wait or fail with a "state locked" message rather than racing).

<details>
<summary>Solution / walkthrough</summary>

```bash
# One-time bootstrap (NOT part of the module-based config below)
aws s3api create-bucket --bucket ashish-tf-lab3-state --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-bucket-versioning --bucket ashish-tf-lab3-state \
  --versioning-configuration Status=Enabled

aws dynamodb create-table \
  --table-name terraform-state-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

```hcl
# modules/s3-bucket/variables.tf
variable "bucket_name" {
  type = string
}

variable "versioning_enabled" {
  type    = bool
  default = true
}

variable "lifecycle_expiration_days" {
  type    = number
  default = 365
}

variable "tags" {
  type    = map(string)
  default = {}
}
```

```hcl
# modules/s3-bucket/main.tf
resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = var.versioning_enabled ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    id     = "expire-old-objects"
    status = "Enabled"
    expiration { days = var.lifecycle_expiration_days }
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

```hcl
# modules/s3-bucket/outputs.tf
output "bucket_arn"  { value = aws_s3_bucket.this.arn }
output "bucket_name" { value = aws_s3_bucket.this.id }
```

```hcl
# root main.tf
terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  backend "s3" {
    bucket         = "ashish-tf-lab3-state"
    key            = "lab3/buckets/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "terraform-state-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = "ap-south-1"
}

module "uploads_bucket" {
  source                    = "./modules/s3-bucket"
  bucket_name               = "ashish-tf-lab3-uploads"
  lifecycle_expiration_days = 90
  tags                      = { Team = "backend" }
}

module "audit_logs_bucket" {
  source                    = "./modules/s3-bucket"
  bucket_name               = "ashish-tf-lab3-audit-logs"
  lifecycle_expiration_days = 2555
  tags                      = { Team = "security" }
}

output "uploads_bucket_arn"    { value = module.uploads_bucket.bucket_arn }
output "audit_logs_bucket_arn" { value = module.audit_logs_bucket.bucket_arn }
```

```bash
terraform init      # re-run whenever you add a module source
terraform plan
terraform apply
```

**On the concurrent-apply test:** the second `terraform apply` should print something like `Error: Error acquiring the state lock ... ConditionalCheckFailedException` — that's DynamoDB's conditional write rejecting the second lock holder. This is the exact failure mode the lesson file's Interview Angle question describes, and you just reproduced (and prevented) it yourself instead of only reading about it.

Clean up: `terraform destroy`, then manually empty and delete the bootstrap state bucket and DynamoDB table if you don't want to keep paying for them (both are free-tier eligible at this scale, but good hygiene either way).
</details>

---

## Lab 4: Troubleshooting — Detecting and Reconciling State Drift

**Objective:** Practice the single most common real-world Terraform incident: someone (or something) changed a resource outside Terraform, and now `plan` shows a confusing diff.

**Task:**
1. Reuse the Lab 1 or Lab 2 bucket (re-apply it if you already destroyed it).
2. Outside Terraform entirely, use the AWS CLI or console to manually disable versioning on the bucket: `aws s3api put-bucket-versioning --bucket <name> --versioning-configuration Status=Suspended`.
3. Run `terraform plan` (no changes to your `.tf` files) and observe what it reports.
4. Explain in your own words why Terraform shows a diff even though you didn't touch any config file.
5. Reconcile it two different ways in two separate attempts: (a) `terraform apply` to force the real world back to match your config, and (b) instead, edit your `.tf` file to match the drifted reality and re-run `plan` to confirm zero diff.
6. Bonus: run `terraform state show aws_s3_bucket_versioning.this` and compare it against the live AWS state before and after step 5.

<details>
<summary>Solution / walkthrough</summary>

```bash
# Manually drift the resource outside Terraform
aws s3api put-bucket-versioning --bucket ashish-tf-lab1-8823 \
  --versioning-configuration Status=Suspended

# Terraform notices on the next plan/apply refresh
terraform plan
```

Expected output shape:
```
  # aws_s3_bucket_versioning.this will be updated in-place
  ~ resource "aws_s3_bucket_versioning" "this" {
        ...
      ~ versioning_configuration {
          ~ status = "Suspended" -> "Enabled"
        }
    }
```

**Why this happens:** every `plan`/`apply` starts with a refresh — Terraform asks AWS's real API "does this resource still look like what my state file says?" It found a mismatch (state says "Enabled", AWS says "Suspended") and computed the diff needed to reconcile config → reality, exactly as described in the lesson file's "State" section.

**Reconciliation path (a) — config wins:**
```bash
terraform apply     # pushes versioning back to Enabled, overwriting the manual change
```

**Reconciliation path (b) — reality wins:** edit `versioning_configuration { status = "Suspended" }` in `main.tf`, then:
```bash
terraform plan       # should now report "No changes"
```

**The lesson to take away:** Terraform doesn't know or care who changed something outside it — every `plan` treats the live infrastructure as the source of truth for "what currently exists" and your `.tf` files as the source of truth for "what should exist." Drift is any gap between those two, and reconciling it always means picking one side to win. In a team setting, path (a) (config wins) is almost always correct — manual console changes to Terraform-managed resources are themselves the anti-pattern to fix, not something to encode into your `.tf` files as a matter of habit.
</details>

---

## Self-Check Checklist

- [ ] Can you explain, without looking it up, what `terraform init` actually downloads/configures?
- [ ] Can you write a `variable` block with a `validation` condition from memory?
- [ ] Can you explain why `sensitive = true` on an output does NOT make the value safe in the state file?
- [ ] Can you write a minimal reusable module (`variables.tf` + `main.tf` + `outputs.tf`) and call it twice with different inputs?
- [ ] Can you explain what problem an S3 + DynamoDB backend solves that a local `terraform.tfstate` file does not?
- [ ] Can you describe, in one sentence, what `terraform workspace` gives you and its one honest limitation?
- [ ] Can you read a `terraform plan` diff and correctly identify a "forces replacement" line before it destroys a stateful resource?
- [ ] Can you explain why HashiCorp calls provisioners a "last resort," and name the two alternatives (cloud-init/user_data, and a dedicated config-management tool)?
- [ ] Given a `terraform plan` showing unexpected drift, can you name both reconciliation strategies and when each is appropriate?
- [ ] Can you explain, out loud, the "Terraform provisions, Ansible configures" division of labor and why this track sequences the two phases that way?
