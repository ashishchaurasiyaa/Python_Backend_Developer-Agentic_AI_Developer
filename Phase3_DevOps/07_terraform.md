# Terraform — IaC Basics, AWS Resource Provisioning

## Quick Concepts
- **Terraform** = Infrastructure as Code (IaC) — code se infrastructure banao
- **Provider** = AWS, GCP, Azure etc. ke saath communicate karta hai
- **Resource** = ek infrastructure piece (EC2, S3, RDS)
- **State** = terraform ka current infrastructure ka record (`terraform.tfstate`)
- **Plan** = kya change hoga dikhata hai (dry run)
- **Apply** = changes actually karta hai

---

## Interview Questions & Answers

### Q1: Terraform kya hai aur kyu use karte hain?
**Answer:**
Terraform HashiCorp ka IaC tool hai. Isse:
- Infrastructure **code mein define** hoti hai (version control possible)
- Same config se **multiple environments** (dev/staging/prod) banao
- Changes ka **dry run** dekh sakte ho `terraform plan` se
- **Idempotent** hai — baar baar apply karo, same result

```hcl
# main.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "my-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "ap-south-1"
  }
}

provider "aws" {
  region = var.aws_region
}
```

---

### Q2: EC2 instance Terraform se kaise create karte hain?
**Answer:**
```hcl
# variables.tf
variable "aws_region" {
  default = "ap-south-1"
}

variable "instance_type" {
  default = "t3.micro"
}

variable "app_name" {
  default = "myapp"
}

# ec2.tf
# Security Group
resource "aws_security_group" "app_sg" {
  name        = "${var.app_name}-sg"
  description = "Allow HTTP, HTTPS, SSH"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["YOUR_IP/32"]     # sirf apna IP SSH ke liye
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Key pair
resource "aws_key_pair" "app_key" {
  key_name   = "${var.app_name}-key"
  public_key = file("~/.ssh/id_rsa.pub")
}

# EC2 Instance
resource "aws_instance" "app_server" {
  ami                    = "ami-0f58b397bc5c1f2e8"   # Ubuntu 22.04 ap-south-1
  instance_type          = var.instance_type
  key_name               = aws_key_pair.app_key.key_name
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.app_profile.name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = <<-EOF
    #!/bin/bash
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker ubuntu
  EOF

  tags = {
    Name        = "${var.app_name}-server"
    Environment = "production"
  }
}

# Elastic IP (static IP)
resource "aws_eip" "app_eip" {
  instance = aws_instance.app_server.id
  domain   = "vpc"
}

# Output
output "server_ip" {
  value = aws_eip.app_eip.public_ip
}
```

---

### Q3: S3 bucket aur RDS Terraform se kaise banate hain?
**Answer:**
```hcl
# s3.tf
resource "aws_s3_bucket" "app_uploads" {
  bucket = "${var.app_name}-uploads-${random_string.suffix.result}"
}

resource "aws_s3_bucket_versioning" "app_uploads_versioning" {
  bucket = aws_s3_bucket.app_uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "app_uploads_public_access" {
  bucket                  = aws_s3_bucket.app_uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

# rds.tf
resource "aws_db_subnet_group" "app_db_subnet" {
  name       = "${var.app_name}-db-subnet"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "app_postgres" {
  identifier        = "${var.app_name}-db"
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "myappdb"
  username = "appuser"
  password = var.db_password   # sensitive variable — .tfvars ya env var se

  vpc_security_group_ids = [aws_security_group.db_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.app_db_subnet.name

  backup_retention_period = 7
  multi_az                = true     # production ke liye
  deletion_protection     = true     # accidental delete se bachao

  skip_final_snapshot = false
  final_snapshot_identifier = "${var.app_name}-final-snapshot"

  tags = {
    Environment = "production"
  }
}

output "rds_endpoint" {
  value     = aws_db_instance.app_postgres.endpoint
  sensitive = true
}
```

---

### Q4: IAM Role + Instance Profile Terraform se kaise banate hain?
**Answer:**
```hcl
# iam.tf
# IAM Role
resource "aws_iam_role" "app_role" {
  name = "${var.app_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

# S3 permissions
resource "aws_iam_role_policy" "app_s3_policy" {
  name = "${var.app_name}-s3-policy"
  role = aws_iam_role.app_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.app_uploads.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.app_uploads.arn
      }
    ]
  })
}

# Instance Profile (EC2 ko role attach karne ke liye)
resource "aws_iam_instance_profile" "app_profile" {
  name = "${var.app_name}-profile"
  role = aws_iam_role.app_role.name
}
```

---

### Q5: Terraform workflow kya hai? Commands kya hain?
**Answer:**
```bash
# 1. Initialize — providers download karo
terraform init

# 2. Format — code format karo
terraform fmt

# 3. Validate — syntax check karo
terraform validate

# 4. Plan — kya change hoga dekho (DRY RUN)
terraform plan
terraform plan -out=tfplan           # plan save karo
terraform plan -var="db_password=secret"

# 5. Apply — actually create/change karo
terraform apply
terraform apply tfplan               # saved plan se
terraform apply -auto-approve        # prompt nahi — CI/CD ke liye

# 6. Destroy — sab delete karo
terraform destroy
terraform destroy -target=aws_instance.app_server  # specific resource

# State management
terraform state list                 # sabhi resources
terraform state show aws_instance.app_server
terraform import aws_instance.app_server i-1234567890  # existing resource import

# Workspace (multiple envs)
terraform workspace new staging
terraform workspace select production
terraform workspace list
```

---

### Q6: Modules kya hain? Reusable infrastructure kaise banate hain?
**Answer:**
```hcl
# modules/ec2_app/main.tf
variable "app_name" {}
variable "instance_type" { default = "t3.micro" }
variable "key_name" {}

resource "aws_instance" "app" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type
  key_name      = var.key_name
  tags = { Name = var.app_name }
}

output "instance_id" { value = aws_instance.app.id }
output "public_ip"   { value = aws_instance.app.public_ip }

# Root main.tf — module use karo
module "prod_app" {
  source        = "./modules/ec2_app"
  app_name      = "myapp-prod"
  instance_type = "t3.small"
  key_name      = "prod-key"
}

module "staging_app" {
  source        = "./modules/ec2_app"
  app_name      = "myapp-staging"
  instance_type = "t3.micro"
  key_name      = "staging-key"
}
```

---

## terraform.tfvars — Sensitive Values

```hcl
# terraform.tfvars (NEVER commit to git!)
db_password = "supersecretpassword"
aws_region  = "ap-south-1"

# .gitignore mein add karo:
# *.tfvars
# *.tfstate
# .terraform/
```
