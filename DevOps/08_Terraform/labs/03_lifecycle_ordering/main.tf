# TODO lab: by default, when Terraform must REPLACE a resource (some change
# forces destroy+recreate, not an in-place update), it destroys the OLD one
# FIRST, then creates the new one. For a single dev machine that's a
# non-issue. For anything actually serving traffic -- a server behind a load
# balancer, a DNS record -- that ordering means a gap where NOTHING is
# serving: the old one is gone and the new one doesn't exist yet.
#
# `create_before_destroy = true` in a `lifecycle` block flips that order:
# Terraform creates the replacement FIRST, waits for it to succeed, and only
# THEN destroys the old one -- no gap. verify.sh proves the actual order by
# parsing `terraform apply -json`'s own machine-readable event stream (the
# same log format tools like Atlantis and CI pipelines consume) -- not by
# guessing from timing.
#
# YOUR TASK: add a lifecycle block to the resource below with
# create_before_destroy = true.
terraform {
  required_providers {
    null = { source = "hashicorp/null", version = "~> 3.2" }
  }
}

variable "version_tag" {
  type    = string
  default = "v1"
}

resource "null_resource" "server" {
  triggers = {
    version = var.version_tag
  }

  # TODO: add lifecycle { create_before_destroy = true } here
}
