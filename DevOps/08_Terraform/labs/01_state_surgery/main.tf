# TODO lab: Terraform tracks resources by ADDRESS (resource type + name in
# your .tf files), not by what they actually are in reality. If you rename a
# resource block -- even without changing anything about the real resource --
# Terraform sees "an address I don't recognize" and an "old address that's
# gone", and its default move is: destroy the old one, create a new one under
# the new address. For a `random_id` that just means a new random value; for
# a real S3 bucket or RDS instance, that's actual data loss.
#
# This is exactly what happened here: `_before/main.tf` (already applied by
# verify.sh, simulating infra someone deployed weeks ago) named the resource
# `random_id.server_a`. This file renames it to `random_id.web_a` -- a
# perfectly reasonable rename (the resource represents a "web" server, not a
# generic "server") -- but WITHOUT telling Terraform they're the same thing.
#
# YOUR TASK: add a `moved` block below telling Terraform that
# `random_id.server_a` (the old address) became `random_id.web_a` (the new
# one), so `terraform apply` updates the state in place instead of
# destroying and recreating the resource:
#
#   moved {
#     from = random_id.server_a
#     to   = random_id.web_a
#   }
terraform {
  required_providers {
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}

resource "random_id" "web_a" {
  byte_length = 8
}

# TODO: add a `moved` block here (from random_id.server_a to random_id.web_a)

output "web_a_hex" {
  value = random_id.web_a.hex
}
