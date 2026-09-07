# Not part of the exercise itself -- verify.sh applies THIS first to create
# the "already-deployed" resource under its OLD name, before you rename it
# in ../main.tf. Don't edit this file.
terraform {
  required_providers {
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}

resource "random_id" "server_a" {
  byte_length = 8
}

output "server_a_hex" {
  value = random_id.server_a.hex
}
