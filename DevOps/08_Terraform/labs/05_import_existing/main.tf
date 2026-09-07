# TODO lab: `tf-lab-imported-bucket` already exists -- verify.sh creates it
# directly via the AWS CLI, with a marker object inside it, BEFORE you ever
# run Terraform. This simulates the extremely common real situation: some
# infra was click-ops'd or CLI'd into existence by someone, months ago, and
# now it needs to come under Terraform management WITHOUT being destroyed
# and recreated (that would delete everything inside it).
#
# `../01_terraform_iac.md` covers `terraform import` in theory (the
# "Adopting Existing Infrastructure" section). This lab makes it real,
# against LocalStack -- no AWS account or cost needed.
#
# YOUR TASK: add an `import` block below telling Terraform that the
# `aws_s3_bucket.adopted` resource this file declares corresponds to the
# ALREADY-EXISTING bucket named `tf-lab-imported-bucket`:
#
#   import {
#     to = aws_s3_bucket.adopted
#     id = "tf-lab-imported-bucket"
#   }
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    s3 = "http://localhost:4566"
  }
}

resource "aws_s3_bucket" "adopted" {
  bucket = "tf-lab-imported-bucket"
}

# TODO: add an `import` block here (to = aws_s3_bucket.adopted,
# id = "tf-lab-imported-bucket")
