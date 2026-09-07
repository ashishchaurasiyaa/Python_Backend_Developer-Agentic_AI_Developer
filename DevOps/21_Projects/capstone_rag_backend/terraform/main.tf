terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state with locking — S3 bucket + DynamoDB table must exist BEFORE
  # this backend block works (create them once, manually or in a separate
  # bootstrap Terraform config that itself uses local state — chicken/egg
  # problem every team hits, this is the standard resolution).
  #
  # bucket/key/region/dynamodb_table can't use variables here — Terraform
  # backend config is evaluated before variables are available. Pass them
  # via `-backend-config` flags or a backend.hcl file per environment instead:
  #   terraform init -backend-config=environments/dev.backend.hcl
  backend "s3" {
    bucket         = "CHANGE-ME-rag-backend-tfstate"
    key            = "rag-backend/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "CHANGE-ME-rag-backend-tf-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type        = string
  description = "dev or prod — set via -var-file"
}

variable "instance_type" {
  type = string
}

variable "db_instance_class" {
  type = string
}

variable "allowed_ssh_cidr" {
  type = string
}

variable "key_name" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
  # No default on purpose — must come from TF_VAR_db_password or a secrets
  # manager at apply time, never from a committed .tfvars file.
}

module "networking" {
  source      = "./modules/networking"
  environment = var.environment
}

module "ec2" {
  source           = "./modules/ec2"
  environment      = var.environment
  vpc_id           = module.networking.vpc_id
  subnet_id        = module.networking.public_subnet_ids[0]
  instance_type    = var.instance_type
  allowed_ssh_cidr = var.allowed_ssh_cidr
  key_name         = var.key_name
}

module "rds" {
  source                 = "./modules/rds"
  environment            = var.environment
  vpc_id                 = module.networking.vpc_id
  db_subnet_group_name   = module.networking.db_subnet_group_name
  app_security_group_id  = module.ec2.security_group_id
  db_instance_class      = var.db_instance_class
  db_password            = var.db_password
}

output "app_url" {
  value = "http://${module.ec2.public_ip}"
}

output "db_endpoint" {
  value     = module.rds.endpoint
  sensitive = true
}
