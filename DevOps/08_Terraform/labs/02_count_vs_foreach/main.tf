terraform {
  required_providers {
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}

variable "names" {
  type    = list(string)
  default = ["a", "b", "c"]
}

# FIXED CONTRAST CASE -- kept exactly as `count` on purpose, to show the bug.
# Do not change this block.
resource "random_id" "count_based" {
  count       = length(var.names)
  byte_length = 4
  keepers = {
    name = var.names[count.index]
  }
}

output "count_based_hex" {
  value = { for i, r in random_id.count_based : var.names[i] => r.hex }
}

# TODO lab: this block is currently a copy-paste of the count_based one
# above -- same bug. `count` identifies resources by POSITION (index 0, 1,
# 2...). If you remove an item from the MIDDLE of var.names, everything
# AFTER that position shifts down one slot, and Terraform sees "the thing at
# index 1 changed" even for a resource that, conceptually, was never touched.
# `for_each` identifies resources by a stable KEY (here, the name itself) --
# removing "b" only touches the resource keyed "b", nothing else moves.
#
# YOUR TASK, two changes:
#   1. In this resource block: replace `count = length(var.names)` with
#      `for_each = toset(var.names)`, and change the keeper from
#      `var.names[count.index]` to `each.value`.
#   2. In the output block below: replace the for-expression's `var.names[i]`
#      indexing with `k` (for_each's natural key), i.e.
#      `{ for k, r in random_id.foreach_based : k => r.hex }`
resource "random_id" "foreach_based" {
  count       = length(var.names) # TODO: for_each = toset(var.names)
  byte_length = 4
  keepers = {
    name = var.names[count.index] # TODO: each.value
  }
}

output "foreach_based_hex" {
  value = { for i, r in random_id.foreach_based : var.names[i] => r.hex } # TODO: { for k, r in random_id.foreach_based : k => r.hex }
}
