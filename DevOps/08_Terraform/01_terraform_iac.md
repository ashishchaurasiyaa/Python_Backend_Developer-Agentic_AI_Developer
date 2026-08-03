# Terraform — Infrastructure as Code
**DevOps Track · Phase 8: Terraform**

> Complementary to Backend_Developer/01_Year3-4_Mid/04_DevOps/ (app-deployment angle) — this covers the fuller AWS/Terraform service and design-pattern picture.

## Quick Concepts

- **IaC (Infrastructure as Code)** = defining infrastructure in versioned, declarative config files instead of clicking in a console
- **Provider** = a plugin that lets Terraform talk to a specific API (AWS, GCP, Azure, Kubernetes, GitHub...)
- **Resource** = a single infrastructure object Terraform manages (an EC2 instance, an S3 bucket, an IAM role)
- **Data Source** = a read-only lookup of something that already exists, not managed by this config
- **Variable** = a parameterized input to a Terraform configuration
- **Output** = a value exposed after `apply`, consumable by humans or other Terraform configs
- **Module** = a reusable, packaged group of resources — Terraform's unit of abstraction/reuse
- **State** = Terraform's record of what it believes exists in the real world, mapped to your config
- **Backend** = where Terraform stores that state file (local disk, S3, Terraform Cloud, etc.)
- **Workspace** = a named, isolated instance of state within the same configuration (e.g. dev/staging/prod)
- **Provisioner** = a last-resort mechanism to run a script on a resource after creation
- **`for_each` / `count`** = meta-arguments that turn one resource block into N instances, driven by a set/map or a number
- **`lifecycle`** = a meta-argument block controlling how Terraform handles create/destroy/change ordering for a resource
- **Drift** = the real world no longer matches what state says it should be (someone changed something outside Terraform)
- **Policy as Code** = automated, codified rules (Sentinel, OPA, or scanners like tfsec/Checkov) that gate a `plan` before `apply` is allowed
- **Atlantis** = an open-source tool that runs `terraform plan`/`apply` from pull request comments, the common self-hosted alternative to Terraform Cloud's PR workflow
- **`.terraform.lock.hcl`** = records the EXACT resolved provider versions/hashes `terraform init` selected — commit this to git, same reasoning as a package-lock.json
- **`-replace`** = force one specific resource to be destroyed and recreated on the next apply, even with no config change (replaces the older `terraform taint`)

---

## Why This Matters

Clicking through the AWS console to build a VPC, EC2 instances, security groups, and an RDS database works exactly once — the moment you need a second identical environment (staging that mirrors prod), or need to prove to an auditor exactly what changed and when, console-clicking falls apart. It's not reproducible, not reviewable in a pull request, and not diffable.

Terraform makes infrastructure a **declarative, versioned artifact**: you describe the desired end state, Terraform computes the diff against the last known state and the real world, and applies only what changed. The same file that provisioned staging provisions prod — with different variable values, not different logic. This is the practical difference between "I deployed infrastructure once" and "I can rebuild this entire environment from git in twenty minutes," which is exactly the claim a senior/DevOps-leaning engineer needs to be able to back up in an interview.

---

## Terraform vs OpenTofu — Why Two Names Exist Now

```
In 2023, HashiCorp changed Terraform's license from open-source (MPL
2.0) to the Business Source License (BSL) — which restricts building
competing commercial products on top of it. In response, the Linux
Foundation forked the last MPL-licensed version and created OpenTofu:
a fully open-source, drop-in-compatible continuation.

Practical reality for you: the HCL syntax, providers, state format,
and everything covered in this file are IDENTICAL between the two —
OpenTofu is a fork, not a rewrite. `terraform` and `tofu` CLI commands
are near 1:1. Some orgs (especially ones wary of BSL terms, or using
Terraform Cloud alternatives like Spacelift/env0) have migrated to
OpenTofu; most still run standard Terraform. Know that both exist and
why, because "which one does your org use, and why" is now a
legitimate interview question where it wasn't before 2023.
```

---

## Day-to-Day Terraform CLI — Commands You'll Actually Run

The End-to-End Example later in this file shows the core loop (`init`/`validate`/`plan`/`apply`/`destroy`). Here's everything else you'll reach for constantly but that loop doesn't cover.

### Formatting and Inspection

```bash
terraform fmt                  # rewrite .tf files to canonical formatting
                                  # (indentation, alignment) — run this before
                                  # every commit, or enforce it in CI
terraform fmt -check             # exit non-zero if formatting is wrong, WITHOUT
                                    # rewriting — what a CI lint step actually uses
terraform fmt -recursive           # format every .tf file in subdirectories too
                                      # (modules/, envs/, etc.)

terraform show                       # human-readable dump of the CURRENT state
terraform show -json                   # same, machine-readable — useful for
                                          # piping into a policy-as-code scanner
                                          # (Phase 8's Policy as Code section) or
                                          # a custom cost/compliance script

terraform providers                      # list every provider this config
                                            # actually requires, and where each
                                            # one comes from
terraform console                          # interactive REPL for testing HCL
                                              # expressions against real state —
                                              # e.g. type `aws_instance.app.public_ip`
                                              # and see the actual value, without
                                              # a full plan/apply cycle
```

### State Inspection and Surgery

```bash
terraform state list                    # every resource address currently
                                           # tracked in state
terraform state show aws_instance.app     # full attributes of ONE resource,
                                             # straight from state (faster than
                                             # digging through `terraform show`
                                             # output for one resource)
terraform state mv aws_instance.web aws_instance.app   # rename a resource's
                                                          # address in state
                                                          # WITHOUT destroying/
                                                          # recreating it — the
                                                          # imperative equivalent
                                                          # of a `moved` block
                                                          # (shown later in this file)
terraform state rm aws_instance.legacy      # stop tracking a resource — Terraform
                                               # forgets about it entirely but does
                                               # NOT delete the real infrastructure;
                                               # use when something should no longer
                                               # be Terraform-managed at all
```

### Targeting and Forcing Replacement

```bash
terraform apply -target=aws_instance.app    # plan/apply ONLY this resource
                                               # (and its dependencies) — an escape
                                               # hatch for "I need to fix just this
                                               # one thing fast," NOT a substitute
                                               # for a properly scoped config.
                                               # HashiCorp's own docs warn against
                                               # relying on -target regularly — it
                                               # can leave your state and config
                                               # subtly out of sync if overused

terraform apply -replace=aws_instance.app     # force this ONE resource to be
                                                 # destroyed and recreated on the
                                                 # next apply, even though nothing
                                                 # about its config changed — the
                                                 # modern replacement for the older
                                                 # `terraform taint aws_instance.app`
                                                 # command (still works, but -replace
                                                 # is the current recommended way)
```

```
Real use case for -replace: an EC2 instance is in a corrupted state
that only a fresh instance fixes, but nothing in your .tf config
actually changed — there's no config diff for Terraform to detect on
its own, so you have to explicitly TELL it to recreate that one resource.
```

### Recovering From a Stuck Lock

```bash
terraform force-unlock <lock-id>     # manually release a state lock that got
                                        # stuck — e.g. someone's apply was killed
                                        # (Ctrl+C, CI job cancelled, laptop died)
                                        # mid-run and never released the DynamoDB
                                        # lock from the State Locking section
                                        # later in this file
```

```
Only run this if you're CERTAIN no other apply is actually in
progress — force-unlock exists specifically for "I know this lock is
stale," not "I'm impatient and don't want to wait." Forcing a lock
open while another apply is genuinely still running recreates exactly
the concurrent-write corruption locking exists to prevent.
```

---

## Providers

A provider is how Terraform authenticates to and calls a specific platform's API.

```hcl
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
  region = var.aws_region
  default_tags {
    tags = {
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}
```

```
required_version   → pins the Terraform CLI version this config expects,
                      protects against a teammate on an incompatible version
                      silently producing a different plan
required_providers → pins the provider plugin version — provider APIs
                      change between major versions, an unpinned provider
                      is a classic source of "it worked yesterday" breakage
default_tags        → applies to EVERY resource this provider creates,
                      without repeating tags = {...} on every single
                      resource block — real cost-allocation hygiene
```

### `.terraform.lock.hcl` — Should This Be Committed to Git?

```bash
terraform init     # creates/updates .terraform.lock.hcl automatically
```

```
required_providers (above) pins a VERSION CONSTRAINT (~> 5.0 — "any
5.x"). .terraform.lock.hcl pins the EXACT resolved version (and
cryptographic hashes) that `terraform init` actually selected and
downloaded — the difference between "roughly what we want" and
"exactly what we got, verified."

YES, commit .terraform.lock.hcl to git — same reasoning as committing
a package-lock.json or poetry.lock: without it, a teammate running
`terraform init` next week could resolve a DIFFERENT patch version
within the same "~> 5.0" constraint, potentially behaving subtly
differently. The lock file is what makes "same config, same provider
version, every time, for everyone" an actual guarantee instead of a hope.
```

---

## Variables

```hcl
variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment name"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "instance_type" {
  description = "EC2 instance type for the app server"
  type        = string
  default     = "t3.micro"
}

variable "allowed_ssh_cidr" {
  description = "CIDR block permitted to SSH into instances"
  type        = string

  validation {
    condition     = can(cidrhost(var.allowed_ssh_cidr, 0))
    error_message = "allowed_ssh_cidr must be a valid CIDR block."
  }
}
```

Variable **validation** blocks turn a typo or bad input ("prodd" instead of "prod", or a malformed CIDR) into an immediate, clear plan-time error instead of a confusing failure three resources deep into apply — this is a frequently underused feature that's an easy senior-level signal in a code review.

Supplying values:

```bash
# terraform.tfvars (checked into git for non-secret defaults)
environment      = "staging"
instance_type    = "t3.small"
allowed_ssh_cidr = "10.0.0.0/16"

# Or per-environment files
terraform apply -var-file="envs/prod.tfvars"

# Or environment variables (TF_VAR_ prefix)
export TF_VAR_environment=prod
```

---

## Creating Multiple Resources — `count`, `for_each`, and Dynamic Blocks

Copy-pasting a resource block three times to create three subnets is the single most common Terraform anti-pattern people write before learning this section.

### `count` — Simple Numeric Repetition

```hcl
resource "aws_instance" "worker" {
  count         = 3
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.small"

  tags = {
    Name = "worker-${count.index}"   # worker-0, worker-1, worker-2
  }
}
```

```
count.index gives each instance a 0-based position, but it's a fragile
identity: if you remove the MIDDLE element (index 1) from a list count
is iterating over, Terraform shifts every index after it — index 2
becomes index 1 — and Terraform sees that as "destroy old index 1,
old index 2 gets renamed/recreated as index 1," not "just remove the
one I deleted." This is the #1 reason `for_each` is preferred whenever
the collection isn't a fixed, never-reordered number.
```

### `for_each` — Keyed Repetition (the Safer Default)

```hcl
variable "subnets" {
  type = map(object({
    cidr = string
    az   = string
  }))
  default = {
    "private-a" = { cidr = "10.0.11.0/24", az = "ap-south-1a" }
    "private-b" = { cidr = "10.0.12.0/24", az = "ap-south-1b" }
    "private-c" = { cidr = "10.0.13.0/24", az = "ap-south-1c" }
  }
}

resource "aws_subnet" "private" {
  for_each          = var.subnets
  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az

  tags = {
    Name = "private-${each.key}"   # private-private-a, etc. (fix naming as needed)
  }
}
```

```
for_each keys each created resource by a STABLE STRING ("private-a"),
not a shifting numeric position. Removing "private-b" from the map
destroys exactly aws_subnet.private["private-b"] and leaves
"private-a" and "private-c" completely untouched — no cascading
replacement of unrelated resources. This is why for_each is the
senior-default choice; count is fine only for truly fixed, order-
independent counts (e.g. "always exactly 3 identical NAT gateways,
never fewer, never reordered").
```

Referencing a `for_each` resource elsewhere uses the key, not an index:

```hcl
output "private_subnet_ids" {
  value = { for k, s in aws_subnet.private : k => s.id }
}
```

### Dynamic Blocks — Repeating a NESTED Block, Not a Whole Resource

`count`/`for_each` repeat entire resources. **`dynamic`** repeats a nested block *inside* one resource — e.g., a security group with a variable number of ingress rules.

```hcl
variable "ingress_rules" {
  type = list(object({
    port        = number
    description = string
    cidr_blocks = list(string)
  }))
  default = [
    { port = 443, description = "HTTPS", cidr_blocks = ["0.0.0.0/0"] },
    { port = 22,  description = "SSH",   cidr_blocks = ["10.0.0.0/16"] },
  ]
}

resource "aws_security_group" "app" {
  name   = "app-sg"
  vpc_id = aws_vpc.main.id

  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      description = ingress.value.description
      from_port   = ingress.value.port
      to_port     = ingress.value.port
      protocol    = "tcp"
      cidr_blocks = ingress.value.cidr_blocks
    }
  }
}
```

Without `dynamic`, adding a fourth ingress rule variant means hardcoding a fourth `ingress { }` block in every environment that needs it — `dynamic` makes the rule set itself a variable.

### A Few Built-In Functions You'll Use Constantly

```hcl
merge(var.default_tags, { Name = "app-server" })     # shallow-merge two maps
jsonencode({ Version = "2012-10-17", Statement = [] }) # build IAM policy JSON inline
templatefile("${path.module}/user_data.sh.tpl", {      # render a file with variables
  db_host = aws_db_instance.main.endpoint
})
lookup(var.instance_sizes, var.environment, "t3.micro") # map lookup with a default
```

`templatefile` in particular replaces the common anti-pattern of building a multi-line `user_data` bootstrap script via string concatenation inside the `.tf` file itself — the script lives in its own `.tpl` file, reviewable and syntax-highlighted like actual shell.

---

## Outputs

```hcl
output "instance_public_ip" {
  description = "Public IP of the app server"
  value       = aws_instance.app.public_ip
}

output "instance_id" {
  value = aws_instance.app.id
}

output "db_endpoint" {
  description = "RDS connection endpoint"
  value       = aws_db_instance.main.endpoint
  sensitive   = true
}
```

```
sensitive = true  → the value is redacted from CLI output ("<sensitive>")
                    but is STILL stored in plaintext in the state file —
                    this does not replace Secrets Manager for real secrets,
                    it only prevents accidental terminal/log leakage
```

Outputs are how one Terraform config exposes values for humans (`terraform output instance_public_ip`) or for another config to consume via `terraform_remote_state` (covered below).

---

## Modules — Packaging Reuse

A module is just a directory of `.tf` files referenced from elsewhere. Every Terraform config is technically already a module (the "root module") — the pattern below is about deliberately splitting reusable pieces into their own directory.

### A Real Reusable Module — S3 Bucket

```
modules/
└── s3-bucket/
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
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
    expiration {
      days = var.lifecycle_expiration_days
    }
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
output "bucket_arn" {
  value = aws_s3_bucket.this.arn
}

output "bucket_name" {
  value = aws_s3_bucket.this.id
}
```

Using it from the root config:

```hcl
module "uploads_bucket" {
  source                     = "./modules/s3-bucket"
  bucket_name                = "my-app-uploads-${var.environment}"
  versioning_enabled         = true
  lifecycle_expiration_days  = 90
  tags = {
    Team = "backend"
  }
}

module "audit_logs_bucket" {
  source                     = "./modules/s3-bucket"
  bucket_name                = "my-app-audit-logs-${var.environment}"
  versioning_enabled         = true
  lifecycle_expiration_days  = 2555
  tags = {
    Team = "security"
  }
}

output "uploads_bucket_arn" {
  value = module.uploads_bucket.bucket_arn
}
```

Two buckets, each with sane security defaults (public access blocked, versioning, lifecycle) baked into the module — every consumer gets those defaults for free, and a single fix inside the module (say, adding server-side encryption) propagates to every bucket created through it the next time someone runs `terraform apply`. That consistency-by-construction is the entire point of modules — it's not just DRY code, it's a way of encoding your org's security/cost defaults once.

Modules can also come from a registry:

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "prod-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["ap-south-1a", "ap-south-1b", "ap-south-1c"]
  private_subnets = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = false
}
```

---

## The `lifecycle` Meta-Argument — Controlling Create/Destroy Behavior

Every resource accepts an optional `lifecycle` block that overrides Terraform's default create/destroy ordering and change-detection behavior. Three sub-arguments cover almost every real use case.

### `prevent_destroy` — A Safety Rail on Irreplaceable Resources

```hcl
resource "aws_db_instance" "main" {
  identifier = "prod-orders-db"
  # ... engine, instance_class, etc.

  lifecycle {
    prevent_destroy = true
  }
}
```

```
With this set, `terraform destroy` or a `plan` that would replace this
resource FAILS with an explicit error instead of silently proceeding.
It does not stop someone from removing the lifecycle block itself and
trying again — it's a deliberate speed bump against the single most
common Terraform disaster: a `terraform destroy` run against the
wrong workspace/directory taking out the production database along
with everything else in that state file.

Put this on: production databases, the Terraform state bucket itself,
anything where "recreate it" means real data loss, not just downtime.
```

### `create_before_destroy` — Zero-Downtime Replacement

```hcl
resource "aws_launch_template" "app" {
  name_prefix   = "app-server-"
  image_id      = data.aws_ami.ubuntu.id
  instance_type = var.instance_type

  lifecycle {
    create_before_destroy = true
  }
}
```

```
Default behavior when a resource must be replaced: DESTROY the old
one, THEN create the new one — a gap with zero capacity in between.
create_before_destroy flips the order: create the NEW resource first,
confirm it succeeds, only THEN destroy the old one.

Requires name_prefix (not a fixed name) on resources whose name must
be unique, since both old and new briefly coexist. This is the
Terraform-level mechanism behind zero-downtime infrastructure
replacement — the same principle as the rolling-update/blue-green
patterns in Phase 20, just applied to the infrastructure resource
itself instead of the application version running on it.
```

### `ignore_changes` — Tolerating Drift From Outside Terraform

```hcl
resource "aws_autoscaling_group" "app" {
  name                = "app-asg"
  desired_capacity    = 3
  min_size            = 2
  max_size            = 10
  vpc_zone_identifier = var.subnet_ids

  lifecycle {
    ignore_changes = [desired_capacity]
  }
}
```

```
Real scenario this fixes: an Auto Scaling target-tracking POLICY
adjusts desired_capacity constantly based on load — that's outside
Terraform's knowledge. Without ignore_changes, every subsequent
`terraform plan` sees "desired_capacity in AWS is 7, but my config
says 3" and wants to "fix" it back to 3, fighting the autoscaling
policy on every apply. ignore_changes tells Terraform: "manage
everything else about this resource, but never treat drift on THIS
specific attribute as something to correct."

Common ignore_changes targets: desired_capacity on an ASG managed by
a scaling policy, tags added by an external tagging-compliance tool,
an image/AMI ID rotated by a separate deployment pipeline outside
this Terraform config.
```

**Senior framing:** these three cover the entire "how does Terraform coexist with things that aren't Terraform" problem — `prevent_destroy` guards against Terraform destroying what it shouldn't, `create_before_destroy` controls the order when it must replace something, `ignore_changes` tells it what NOT to fight with when something else legitimately owns an attribute.

---

## State — Why It Matters

```
Terraform state (terraform.tfstate) is a JSON file mapping:

    your config's resource addresses  ↔  real-world resource IDs

Without state, Terraform would have no way to know that
"aws_instance.app" in your config IS the EC2 instance with ID
i-0abc123def456 that already exists — it would either try to
recreate it (duplicate resources) or have no idea what to diff against.

Every plan/apply:
  1. Refreshes state (asks the real provider APIs: "does this still
     look like what state says it looks like?")
  2. Diffs desired config against refreshed state
  3. Computes the smallest set of create/update/destroy actions to
     reconcile the two
```

### Drift — When Reality Diverges From State

```
Drift = someone (a human clicking in the console during an incident,
another automation tool, a manual `aws` CLI fix at 2 AM) changed real
infrastructure WITHOUT going through Terraform. State still says the
old value; reality says the new one.

`terraform plan` is itself the drift-detection step — its "refresh"
phase re-queries the real provider APIs before diffing, so an
unexpected plan output (a change you didn't author) is usually drift,
not a bug in your config.
```

```bash
# Refresh-only plan — see drift WITHOUT proposing to fix it yet
terraform plan -refresh-only

# Accept the drifted real-world value INTO state (use when the manual
# change was legitimate and should become the new source of truth)
terraform apply -refresh-only

# Force state back to match config on the next normal apply
# (use when the manual change was NOT legitimate and should be reverted)
terraform apply
```

**Real incident pattern:** an engineer manually bumps an EC2 instance's security group during an outage to unblock something fast, forgets to update the `.tf` file, and the next routine `terraform apply` — run by someone else, days later — silently reverts the security group back to the old (now wrong) value, because Terraform has no idea the manual change was intentional. `terraform plan -refresh-only` on a schedule (or before any apply touching that resource) is the habit that catches this before it becomes a surprise. Hands-on practice: `practical/01_terraform_lab.md` Lab 4.

### State Locking — Why It's Non-Negotiable in a Team

```
Two engineers running `terraform apply` on the SAME state at the SAME
time, with no locking, can corrupt the state file or both partially
apply conflicting changes — a well-known way to have a very bad day.

State locking makes a second `apply` WAIT (or fail loudly) if a lock
is already held, instead of racing.
```

---

## Backend — S3 + DynamoDB Lock

```hcl
terraform {
  backend "s3" {
    bucket         = "my-org-terraform-state"
    key            = "prod/network/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "terraform-state-locks"
    encrypt        = true
  }
}
```

```
bucket + key   → S3 bucket and object path storing the state file;
                 using a different "key" per environment/component
                 (prod/network, prod/database, staging/network) is
                 the standard way to split state so a mistake in one
                 area can't blast-radius into an unrelated one
dynamodb_table → the lock table — Terraform writes a lock item here
                 before any apply and removes it after, using DynamoDB's
                 conditional writes to guarantee only one holder at a time
encrypt        → server-side encryption on the state object — state
                 often contains sensitive values (see the `sensitive`
                 output caveat above), treat the state bucket itself
                 as sensitive infrastructure
```

Bootstrapping this backend (the classic chicken-and-egg: you need infrastructure to store the state that manages your infrastructure) is usually done once, by hand or via a separate minimal bootstrap config, before every other Terraform config points at it:

```bash
aws s3api create-bucket --bucket my-org-terraform-state --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-bucket-versioning --bucket my-org-terraform-state \
  --versioning-configuration Status=Enabled

aws dynamodb create-table \
  --table-name terraform-state-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

---

## Workspaces — Dev/Staging/Prod Pattern

```bash
terraform workspace new dev
terraform workspace new staging
terraform workspace new prod

terraform workspace select prod
terraform apply -var-file="envs/prod.tfvars"
```

```
Each workspace gets its OWN state file (same backend, different state
path suffixed by workspace name) from the SAME configuration — so
"dev" and "prod" are guaranteed to be structurally identical (same
resources, same module calls), differing only in variable values.

terraform.workspace  → available inside config as a string, useful for
                        naming: bucket_name = "my-app-${terraform.workspace}"
```

**Honest caveat worth knowing for interviews**: workspaces are a lightweight isolation mechanism, not a full substitute for separate state files/directories per environment in larger orgs. Many teams outgrow workspaces and move to fully separate root configs per environment (each with its own backend `key`) specifically because workspaces make it too easy to accidentally `apply` against the wrong environment if you forget which one is selected (`terraform workspace show` before every apply is a good habit). Both patterns are legitimate; know the tradeoff rather than treating workspaces as strictly superior.

---

## Remote State — Referencing Another Config's Outputs

When infrastructure is split across multiple Terraform configs/state files (network config, database config, app config — each independently applied), one config can read another's outputs via `terraform_remote_state`:

```hcl
data "terraform_remote_state" "network" {
  backend = "s3"
  config = {
    bucket = "my-org-terraform-state"
    key    = "prod/network/terraform.tfstate"
    region = "ap-south-1"
  }
}

resource "aws_instance" "app" {
  ami           = var.ami_id
  instance_type = var.instance_type
  subnet_id     = data.terraform_remote_state.network.outputs.private_subnet_ids[0]
  vpc_security_group_ids = [
    data.terraform_remote_state.network.outputs.app_security_group_id
  ]
}
```

This is how a database team's config can consume a network team's VPC/subnet IDs without either team needing write access to the other's state — a common pattern once infrastructure grows past a single monolithic config, and a natural way to enforce team ownership boundaries.

---

## Provider Aliases — Multi-Region and Multi-Account in One Config

A single `provider "aws" { }` block is the default region for the whole config. **`alias`** lets one config talk to a second region (or account) for specific resources, without splitting into a separate root config.

```hcl
provider "aws" {
  region = var.aws_region       # e.g. ap-south-1 — the "default" provider
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

resource "aws_acm_certificate" "cdn_cert" {
  provider          = aws.us_east_1     # explicitly use the aliased provider
  domain_name       = "app.example.com"
  validation_method = "DNS"
}

resource "aws_cloudfront_distribution" "cdn" {
  # CloudFront itself is "global," but the ACM cert it references
  # MUST have been issued in us-east-1 — a genuine AWS quirk, not a
  # Terraform one — so this resource references the aliased cert above
  viewer_certificate {
    acm_certificate_arn = aws_acm_certificate.cdn_cert.arn
    ssl_support_method   = "sni-only"
  }
  # ... origin, default_cache_behavior, etc.
}
```

**Why this specific example matters:** "CloudFront + ACM certificate validation fails, cert exists but CloudFront can't see it" is one of the most common real AWS gotchas — the fix is *always* "the cert isn't in us-east-1," regardless of what region the rest of the stack lives in. Knowing to reach for a provider alias here (rather than being confused about why a resource "can't find" a certificate that clearly exists) is a concrete, checkable signal of real AWS experience versus tutorial-only knowledge.

Multi-account (not just multi-region) uses the identical pattern — a second `provider "aws" { alias = "shared_services" assume_role { role_arn = ... } }` block assuming a role in a different account.

---

## Provisioners — Use Sparingly

```hcl
resource "aws_instance" "app" {
  ami           = var.ami_id
  instance_type = var.instance_type

  provisioner "local-exec" {
    command = "echo ${self.public_ip} >> inventory.txt"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y nginx",
    ]
    connection {
      type        = "ssh"
      user        = "ubuntu"
      private_key = file(var.ssh_private_key_path)
      host        = self.public_ip
    }
  }
}
```

```
local-exec   → runs a command on the machine running Terraform, not on
               the resource itself (e.g. update a local inventory file,
               trigger an external webhook)
remote-exec  → SSHes (or WinRM) into the newly created resource and
               runs commands on IT
```

### Why HashiCorp Says "Avoid Provisioners When Possible"

```
Provisioners are explicitly called out in HashiCorp's own documentation
as a LAST RESORT, because:

  - Terraform has no visibility into what a provisioner script actually
    changed — it's opaque to the state/plan/diff model that makes
    Terraform declarative and predictable in the first place
  - No idempotency guarantee — re-running apply may or may not be safe
    depending on what the script does
  - Network/SSH dependency at APPLY time — if the instance isn't
    reachable yet, provisioning can flake, and there's no clean retry
    story built in

Prefer instead:
  - Bake configuration into the AMI ahead of time (Packer)
  - Use cloud-init / EC2 user_data for first-boot bootstrapping
  - Use a dedicated configuration management tool AFTER provisioning
    (Ansible, which is exactly what Phase 9 of this track covers) —
    let Terraform provision the resource, let Ansible configure it
```

This division of labor — **Terraform provisions, Ansible configures** — is a very common senior-level answer to "how do Terraform and Ansible fit together," and directly explains why this track has them as separate, sequential phases.

---

## Adopting Existing Infrastructure — `terraform import` and `moved` Blocks

Two different problems that both come up constantly once Terraform meets a real, already-running environment: bringing in infrastructure that was never created by Terraform, and safely refactoring config that Terraform ALREADY manages.

### `terraform import` — Bringing Existing Infra Under Management

```
Scenario: an S3 bucket was created by hand (or by a previous engineer's
one-off script) months ago, and it's real, in-use production
infrastructure. You want Terraform to manage it going forward WITHOUT
destroying and recreating it (which would delete real data).
```

```hcl
# 1. Write the resource block matching what already exists
resource "aws_s3_bucket" "legacy_uploads" {
  bucket = "legacy-app-uploads"
}
```

```bash
# 2. Import — tells Terraform "this config block IS this real resource"
terraform import aws_s3_bucket.legacy_uploads legacy-app-uploads

# 3. Plan — should show NO changes if your config matches reality exactly
terraform plan
# if it shows changes, your .tf config doesn't yet match the real
# resource's actual settings — adjust the config (not the real
# resource) until plan is clean, THEN it's safely under management
```

```
Newer Terraform versions (1.5+) support import BLOCKS as a declarative
alternative to the imperative `terraform import` command — written
directly in .tf, reviewable in a PR, and can import many resources at
once via `for_each`:

import {
  to = aws_s3_bucket.legacy_uploads
  id = "legacy-app-uploads"
}
```

### `moved` Blocks — Refactoring Without Destroy-Recreate

```
Scenario: you rename a resource (aws_instance.web -> aws_instance.app),
or move it into a module. Terraform's default behavior on a rename is
"the old address is GONE, the new address is NEW" — meaning destroy
the old, create the new. On a stateful resource (a database, a
long-lived instance with local data), that's exactly what you don't want.
```

```hcl
moved {
  from = aws_instance.web
  to   = aws_instance.app
}

resource "aws_instance" "app" {
  # ... same config, just renamed
}
```

```bash
terraform plan
# shows "aws_instance.app will be MOVED from aws_instance.web" —
# a metadata-only state update, NOT a destroy+create
```

```hcl
# Moving a resource INTO a module during a refactor
moved {
  from = aws_instance.app
  to   = module.app_server.aws_instance.app
}
```

**Senior framing — the pattern behind both:** `import` and `moved` solve the same underlying problem from opposite directions — "make Terraform's state match reality without destroying anything real." `import` is for infra that exists outside Terraform's knowledge entirely; `moved` is for infra Terraform already manages, whose *address* in the config needs to change. Referenced in the earlier Interview Angle answer about state corruption recovery — this is the full version of that `state`/`import` toolkit.

---

## End-to-End Example — EC2 Instance + Security Group

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
  backend "s3" {
    bucket         = "my-org-terraform-state"
    key            = "dev/app-server/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "terraform-state-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_vpc" "default" {
  default = true
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_security_group" "app" {
  name        = "${var.environment}-app-sg"
  description = "Security group for the app server"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTPS from anywhere"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH from trusted CIDR only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-app-sg"
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  vpc_security_group_ids = [aws_security_group.app.id]
  key_name                = var.key_pair_name

  user_data = <<-EOF
    #!/bin/bash
    set -euo pipefail
    apt-get update -y
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
  EOF

  tags = {
    Name        = "${var.environment}-app-server"
    Environment = var.environment
  }
}
```

```hcl
# variables.tf
variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "environment" {
  type = string
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

variable "key_pair_name" {
  type = string
}

variable "allowed_ssh_cidr" {
  type = string
}
```

```hcl
# outputs.tf
output "instance_public_ip" {
  value = aws_instance.app.public_ip
}
output "security_group_id" {
  value = aws_security_group.app.id
}
```

```bash
terraform init                            # download providers, configure backend
terraform validate                        # syntax + internal consistency check
terraform plan -var-file="dev.tfvars"     # preview the diff — READ THIS before apply
terraform apply -var-file="dev.tfvars"    # apply after review
terraform destroy -var-file="dev.tfvars"  # tear down (careful, no soft-delete)
```

Note the `data "aws_ami" "ubuntu"` block — a **data source**, not a resource. It doesn't create anything, it looks up the latest matching AMI ID at plan time so the config never hardcodes a specific (and eventually stale/deprecated) AMI ID.

---

## Policy as Code — Scanning Terraform Before Apply

Image/dependency scanning (Phase 14) catches vulnerabilities in what you BUILD. This is the equivalent shift-left practice for what you PROVISION — catching a misconfigured, insecure, or non-compliant resource in the `.tf` code itself, before it's ever applied.

```bash
# tfsec — security-focused static analysis for Terraform
tfsec .
# flags things like: unencrypted S3 buckets, security groups open to
# 0.0.0.0/0 on unexpected ports, IAM policies with wildcard actions

# Checkov — broader policy engine (security + compliance + best practice),
# supports Terraform, CloudFormation, Kubernetes, Dockerfiles in one tool
checkov -d .

# terrascan — similar space, OPA/Rego-based policy engine under the hood
terrascan scan -i terraform
```

```yaml
# .github/workflows/terraform.yml — gate a PR on a clean scan
      - name: tfsec scan
        uses: aquasecurity/tfsec-action@v1.0.3
        with:
          soft_fail: false     # fails the check — blocks merge on findings
```

```
Sentinel (Terraform Cloud/Enterprise's own policy engine) and Open
Policy Agent (OPA, provider-agnostic, used via `terraform plan` JSON
output + conftest) solve the same problem at the ORGANIZATIONAL level
— "no S3 bucket may ever be created without encryption, enforced
centrally, not left to individual engineers remembering to run tfsec
locally." tfsec/Checkov are the right scope for an individual repo/
team; Sentinel/OPA are the right scope once a platform team needs to
enforce the same policy across every team's Terraform, everywhere.
```

**Cost visibility — Infracost:** a related but separate concern from security scanning — Infracost annotates a PR's `terraform plan` with the estimated monthly cost DELTA of the change ("+$340/mo: this PR adds 2 m6i.large instances"), turning a cost surprise from "next month's AWS bill" into "visible in code review, before merge." Increasingly common in PR templates at cost-conscious product companies, worth knowing exists even if you haven't set it up yourself yet.

---

## Atlantis — PR-Based Plan/Apply Automation

The Senior Tip elsewhere in this file says "plan-on-PR, apply-on-merge is the standard GitOps pattern for Terraform in CI/CD" — **Atlantis** is the dedicated open-source tool that implements exactly this, as an alternative to hand-rolling it in raw CI YAML or paying for Terraform Cloud.

```
How it works:
  1. Atlantis runs as a service (self-hosted, webhook-connected to your
     VCS — GitHub/GitLab/Bitbucket)
  2. Someone opens a PR changing .tf files
  3. Atlantis automatically runs `terraform plan`, posts the FULL plan
     output as a PR COMMENT — reviewers see the actual infrastructure
     diff without leaving the PR or running anything locally
  4. A human comments "atlantis apply" on the PR to actually apply —
     apply is a deliberate, auditable action taken by a named person,
     not automatic on merge
  5. PR merges once the applied plan matches what was reviewed
```

```yaml
# atlantis.yaml — repo config
version: 3
projects:
  - name: prod-network
    dir: environments/prod/network
    workflow: default
  - name: prod-database
    dir: environments/prod/database
    workflow: default

workflows:
  default:
    plan:
      steps: [init, plan]
    apply:
      steps: [apply]
```

**Why teams reach for this over plain CI YAML:** the PR comment IS the review artifact (no separate CI log to dig through), multiple engineers can see and discuss a specific plan's line-by-line diff inline on the PR, and Atlantis natively handles state locking across concurrent PRs touching the same project (queues a second `plan` if one is already running against that directory) — a raw GitHub Actions pipeline would need to reimplement all of this by hand. Terraform Cloud's built-in VCS-driven runs are the paid-SaaS equivalent of the same workflow.

---

## Testing Terraform — `terraform test` and Terratest

```
"How do you test infrastructure code" is an increasingly common
senior question — the honest answer for most Terraform code is
`terraform plan` + policy scanning (tfsec/Checkov) IS the primary
test, because most of what could go wrong is a plan-time diff or a
policy violation, not application-style logic. Two dedicated tools
exist for the cases that need more:
```

```hcl
# native `terraform test` (built in since Terraform 1.6) — HCL-based,
# runs a plan/apply against a REAL (usually ephemeral/sandboxed) provider
# tests/vpc.tftest.hcl
run "vpc_has_three_azs" {
  command = plan

  assert {
    condition     = length(module.vpc.private_subnets) == 3
    error_message = "Expected 3 private subnets, one per AZ"
  }
}
```

```bash
terraform test
```

```
Terratest (Gruntwork, Go-based) is the older, more established
alternative — actually applies real infrastructure in a throwaway
account/namespace, runs assertions against it (e.g., "curl this ALB
endpoint and expect a 200"), then destroys it. Heavier and slower than
native `terraform test` (real cloud resources cost money and take
minutes to provision) but able to verify things a plan-only test
can't — that the infrastructure, once actually running, WORKS.

Pragmatic take for where you're likely to land: know both exist and
the tradeoff (fast/plan-only vs slow/real-infra-verified); reach for
Terratest specifically when a bug class you've actually hit was
"the plan looked fine but the deployed thing didn't work."
```

---

## Senior Tip

```
Always run `terraform plan` and actually READ the output before
`apply` — especially watch for unexpected "-/+ (forces replacement)"
lines. Some attribute changes (like changing an RDS instance's storage
type in certain combinations, or renaming a resource without a `moved`
block) force a destroy-and-recreate instead of an in-place update —
on a stateful resource like a database, that's catastrophic if you
don't catch it in the plan.

Never run `terraform apply -auto-approve` against production by habit.
Reserve auto-approve for CI pipelines where the plan output was already
reviewed as part of the pull request (plan-on-PR, apply-on-merge is the
standard GitOps pattern for Terraform in CI/CD).
```

## Interview Angle

**Q: Two engineers both ran `terraform apply` on the same state around the same time and now the state file looks corrupted. How did this happen and how do you prevent it?**

It happened because the backend wasn't configured with state locking (no DynamoDB table, or a local/unlocked backend), so both applies proceeded concurrently and raced to write the state file. Prevent it going forward with an S3 backend + DynamoDB lock table (shown above) — Terraform will make the second `apply` block or fail cleanly instead of corrupting shared state. If corruption already happened, recovery involves `terraform state` subcommands (`state list`, `state show`, `state rm`, `import`) to manually reconcile state against the real infrastructure, or restoring the last good version from the S3 bucket's object versioning history (another reason to enable versioning on the state bucket).

**Q: Why prefer `for_each` over `count` when creating multiple similar resources?**
`for_each` keys each resource by a stable string from a map/set, so removing one element only destroys that specific resource. `count` keys by numeric position — removing an element from the middle of the list Terraform is iterating shifts every subsequent index, causing Terraform to plan destroy/recreate on resources that didn't actually need to change at all. `count` is fine only when the number is truly fixed and order never matters.

**Q: An ASG's `desired_capacity` keeps getting "corrected" back down by `terraform apply`, fighting an autoscaling policy that's actively adjusting it. How do you fix this?**
Add `lifecycle { ignore_changes = [desired_capacity] }` to the ASG resource — this tells Terraform to manage everything else about the resource but never treat drift on that specific attribute as something to reconcile, since an external process (the scaling policy) legitimately owns it.

**Q: You need to rename `aws_instance.web` to `aws_instance.app` in your config without destroying and recreating the real EC2 instance. How?**
A `moved` block (`from = aws_instance.web`, `to = aws_instance.app`) — `terraform plan` then shows the resource as MOVED (a state metadata update) rather than destroyed and recreated. Renaming without a `moved` block is exactly the "forces replacement" trap called out in the Senior Tip above.

**Q: A specific EC2 instance is in a corrupted state, but nothing in your `.tf` config actually changed. How do you force Terraform to recreate just that one resource?**
`terraform apply -replace=aws_instance.app` — this forces that one resource to be destroyed and recreated on the next apply even though Terraform's own diff sees no config change to react to. This is the modern replacement for the older `terraform taint` command, which did the same thing via a separate imperative step instead of a plan/apply flag.

**Q: Should `.terraform.lock.hcl` be committed to git?**
Yes — `required_providers` only pins a version CONSTRAINT (e.g. `~> 5.0`, "any 5.x"), while the lock file records the EXACT resolved version and cryptographic hash `terraform init` actually selected. Without committing it, a teammate running `init` later could resolve a different patch version within the same constraint and get subtly different provider behavior — the same reasoning as committing a `package-lock.json` or `poetry.lock`.

**Q: A `terraform apply` was killed mid-run (Ctrl+C, a cancelled CI job) and now every subsequent apply fails with a state lock error, even though nothing is actually running. What do you do?**
`terraform force-unlock <lock-id>` — but only after confirming no apply is genuinely still in progress anywhere (check with your team, check the CI system's job history). Force-unlocking while another apply IS actually running recreates exactly the concurrent-write corruption that locking exists to prevent in the first place.

---

## Related

- [../09_Ansible/01_ansible_config_mgmt.md](../09_Ansible/01_ansible_config_mgmt.md) — configuring what Terraform provisions
- [../07_Cloud_AWS/01_iam_compute_ec2.md](../07_Cloud_AWS/01_iam_compute_ec2.md) — the AWS resources this file provisions
- [../../Backend_Developer/01_Year3-4_Mid/04_DevOps/07_terraform.md](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/07_terraform.md) — app-deployment-focused Terraform basics
