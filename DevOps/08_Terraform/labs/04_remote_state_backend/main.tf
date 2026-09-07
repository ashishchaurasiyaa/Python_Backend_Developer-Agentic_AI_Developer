# TODO lab: this is the exact "Backend -- S3 + DynamoDB Lock" pattern from
# ../01_terraform_iac.md, made real. Instead of a real AWS account (which
# this lab deliberately avoids -- no cloud account or cost needed), it
# points at LocalStack, a local AWS-API-compatible emulator running via
# ../_setup/docker-compose.yml. The S3 bucket and DynamoDB table below are
# created ahead of time by verify.sh's bootstrap step (mirroring
# ../practical/01_terraform_lab.md Lab 3's own "one-time bootstrap" pattern
# -- a backend's storage has to exist before you can point Terraform at it).
#
# YOUR TASK: this backend block is missing the two settings that redirect it
# from REAL AWS to the LocalStack emulator on localhost:4566. Without them,
# `terraform init` tries to reach real AWS S3/DynamoDB and fails on
# authentication (there's no such AWS account here). Add:
#
#   endpoints = {
#     s3       = "http://localhost:4566"
#     dynamodb = "http://localhost:4566"
#   }
#   use_path_style = true
terraform {
  required_providers {
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }

  backend "s3" {
    bucket = "tf-lab-state"
    key    = "lab4/terraform.tfstate"
    region = "us-east-1"

    dynamodb_table = "tf-lab-locks"

    access_key                  = "test"
    secret_key                  = "test"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_requesting_account_id  = true

    # TODO: add `endpoints = { s3 = "http://localhost:4566", dynamodb = "http://localhost:4566" }`
    # and `use_path_style = true` here
  }
}

resource "random_id" "marker" {
  byte_length = 4
}

output "marker_hex" {
  value = random_id.marker.hex
}
